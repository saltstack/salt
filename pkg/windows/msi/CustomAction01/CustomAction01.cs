using Microsoft.Deployment.WindowsInstaller;
using Microsoft.Tools.WindowsInstallerXml;
using Microsoft.Win32;
using System;
using System.Diagnostics;
using System.IO;
using System.Management;  // Reference C:\Windows\Microsoft.NET\Framework\v2.0.50727\System.Management.dll
using System.Security.AccessControl;
using System.Security.Principal;
using System.ServiceProcess;
using System.Text.RegularExpressions;
using System.Collections.Generic;


namespace MinionConfigurationExtension {
    public class MinionConfiguration : WixExtension {


        [CustomAction]
        public static ActionResult ReadConfig_IMCAC(Session session) {
            /*
            When the installation begins, there may be a previous installation with existing config.
            If existing config is found, we need to verify that it is in a secure state. If it is
            secure then it will be used as is, unchanged.

            We will read the values from existing config to possibly display in the GUI, but it will
            be for informational purposes only. The only CONFIG_TYPES that will be edited are
            DEFAULT and CUSTOM.

            The two config options and their defaults are:
              - master: salt
              - id: hostname

            If the CONFIG_TYPE is not "Existing", and the master and minion id are not the defaults,
            then those values will be used to update either the Default config or a Custom config.

            This function writes msi properties:
              - MASTER
              - MINION_ID
              - CONFIG_TYPE

            A GUI installation can show these msi properties because this function is called before the GUI.
            */
            session.Log("...BEGIN ReadConfig_IMCAC");
            string ProgramData    = System.Environment.GetEnvironmentVariable("ProgramData");

            string oldRootDir = @"C:\salt";
            string newRootDir =  Path.Combine(ProgramData, @"Salt Project\Salt");

            // Create msi proporties
            session["ROOTDIR_old"] = oldRootDir;
            session["ROOTDIR_new"] = newRootDir;

            string abortReason = "";
            // Insert the first abort reason here
            if (abortReason.Length > 0) {
                session["AbortReason"] = abortReason;
            }

            session.Log("...Looking for existing config");
            string REGISTRY_ROOTDIR = session["EXISTING_ROOTDIR"];          // From registry
            string reg_config = "";
            if (REGISTRY_ROOTDIR.Length > 0){
                reg_config = REGISTRY_ROOTDIR + @"\conf\minion";
            }
            // Search for configuration in this order: registry, new layout, old layout
            string minion_config_file = cutil.get_file_that_exist(session, new string[] {
                reg_config,
                newRootDir + @"\conf\minion",
                oldRootDir + @"\conf\minion"});
            string minion_config_dir = "";

            // Check for a minion.d directory
            if (File.Exists(minion_config_file)) {
                string minion_dot_d_dir = minion_config_file + ".d";
                session.Log("...minion_dot_d_dir = " + minion_dot_d_dir);
                if (Directory.Exists(minion_dot_d_dir)) {
                    session.Log("... folder exists minion_dot_d_dir = " + minion_dot_d_dir);
                    DirectorySecurity dirSecurity = Directory.GetAccessControl(minion_dot_d_dir);
                    IdentityReference sid = dirSecurity.GetOwner(typeof(SecurityIdentifier));
                    session.Log("...owner of the minion config dir " + sid.Value);
                } else {
                    session.Log("... folder does not exist: " + minion_dot_d_dir);
                }
            }

            // Check for existing config
            if (File.Exists(minion_config_file)) {
                // We found an existing config
                session["CONFIG_TYPE"] = "Existing";

                // Make sure the directory where the config was found is secure
                minion_config_dir = Path.GetDirectoryName(minion_config_file);
                // Owner must be one of "Local System" or "Administrators"
                // It looks like the NullSoft installer sets the owner to
                // Administrators while the MSI installer sets the owner to
                // Local System. Salt only sets the owner of the `C:\salt`
                // directory when it starts and doesn't concern itself with the
                // conf directory. So we have to check for both.
                List<string> valid_sids = new List<string>();
                valid_sids.Add("S-1-5-18");      //Local System
                valid_sids.Add("S-1-5-32-544");  //Administrators

                // Get the SID for the owner of the conf directory
                FileSecurity fileSecurity = File.GetAccessControl(minion_config_dir);
                IdentityReference sid = fileSecurity.GetOwner(typeof(SecurityIdentifier));
                session.Log("...owner of the minion config file " + sid.Value);

                // Check to see if it's in the list of valid SIDs
                if (!valid_sids.Contains(sid.Value)) {
                    // If it's not in the list we don't want to use it. Do the following:
                    // - set INSECURE_CONFIG_FOUND to the insecure config dir
                    // - set CONFIG_TYPE to Default
                    session.Log("...Insecure config found, using default config");
                    session["INSECURE_CONFIG_FOUND"] = minion_config_dir;
                    session["CONFIG_TYPE"] = "Default";
                    session["GET_CONFIG_TEMPLATE_FROM_MSI_STORE"] = "True";    // Use template instead
                }
            } else {
                session["GET_CONFIG_TEMPLATE_FROM_MSI_STORE"] = "True";    // Use template
            }

            // Set the default values for master and id
            String master_from_previous_installation = "";
            String id_from_previous_installation = "";
            // Read master and id from main config file (if such a file exists)
            if (minion_config_file.Length > 0) {
                read_master_and_id_from_file_IMCAC(session, minion_config_file, ref master_from_previous_installation, ref id_from_previous_installation);
            }
            // Read master and id from minion.d/*.conf (if they exist)
            if (Directory.Exists(minion_config_dir)) {
                var conf_files = System.IO.Directory.GetFiles(minion_config_dir, "*.conf");
                foreach (var conf_file in conf_files) {
                    if (conf_file.Equals("_schedule.conf")) { continue; }            // skip _schedule.conf
                    read_master_and_id_from_file_IMCAC(session, conf_file, ref master_from_previous_installation, ref id_from_previous_installation);
                }
            }

            if (session["MASTER"] == "") {
                session["MASTER"] = "salt";
            }
            if (session["MINION_ID"] == "") {
                session["MINION_ID"] = "hostname";
            }

            session.Log("...CONFIG_TYPE msi property  = " + session["CONFIG_TYPE"]);
            session.Log("...MASTER      msi property  = " + session["MASTER"]);
            session.Log("...MINION_ID   msi property  = " + session["MINION_ID"]);

            // A list of config types that will be edited. Existing config will NOT be edited
            List<string> editable_types = new List<string>();
            editable_types.Add("Default");
            editable_types.Add("Custom");
            if (editable_types.Contains(session["CONFIG_TYPE"])) {
                // master
                if (master_from_previous_installation != "") {
                    session.Log("...MASTER      kept config   =" + master_from_previous_installation);
                    session["MASTER"] = master_from_previous_installation;
                    session["CONFIG_FOUND"] = "True";
                    session.Log("...MASTER set to kept config");
                }

                // minion id
                if (id_from_previous_installation != "") {
                    session.Log("...MINION_ID   kept config   =" + id_from_previous_installation);
                    session.Log("...MINION_ID set to kept config ");
                    session["MINION_ID"] = id_from_previous_installation;
                }
            }

            // Save the salt-master public key
            // This assumes the install is silent.
            // Saving should only occur in WriteConfig_DECAC,
            // IMCAC is easier and no harm because there is no public master key in the installer.
            string MASTER_KEY = cutil.get_property_IMCAC(session, "MASTER_KEY");
            string ROOTDIR    = cutil.get_property_IMCAC(session, "ROOTDIR");
            string pki_minion_dir = Path.Combine(ROOTDIR, @"conf\minion.d\pki\minion");
            var master_key_file = Path.Combine(pki_minion_dir, "minion_master.pub");
            session.Log("...master_key_file           = " + master_key_file);
            bool MASTER_KEY_set = MASTER_KEY != "";
            session.Log("...master key earlier config file exists = " + File.Exists(master_key_file));
            session.Log("...master key msi property given         = " + MASTER_KEY_set);
            if (MASTER_KEY_set) {
                String master_key_lines = "";   // Newline after 64 characters
                int count_characters = 0;
                foreach (char character in MASTER_KEY) {
                    master_key_lines += character;
                    count_characters += 1;
                    if (count_characters % 64 == 0) {
                        master_key_lines += Environment.NewLine;
                    }
                }
                string new_master_pub_key =
                  "-----BEGIN PUBLIC KEY-----" + Environment.NewLine +
                  master_key_lines + Environment.NewLine +
                  "-----END PUBLIC KEY-----";
                if (!Directory.Exists(pki_minion_dir)) {
                    // The <Directory> declaration in Product.wxs does not create the folders
                    Directory.CreateDirectory(pki_minion_dir);
                }
                File.WriteAllText(master_key_file, new_master_pub_key);
            }
            session.Log("...END ReadConfig_IMCAC");
            return ActionResult.Success;
        }


        private static void write_master_and_id_to_file_DECAC(Session session, String config_file, string csv_multimasters, String id) {
            /* How to
             * read line
             * if line master, read multimaster, replace
             * if line id, replace
             * copy through line
            */

            session.Log("...BEGIN write_master_and_id_to_file_DECAC");
            session.Log("...want to write master and id to " + config_file);
            session.Log("......master: " + csv_multimasters);
            session.Log("......id: " + id);

            if (File.Exists(config_file)) {
                session.Log("...config_file exists: " + config_file);
            } else {
                session.Log("......ERROR: no config file found: {0}", config_file);
                return;
            }

            // Load current config
            string config_content = File.ReadAllText(config_file);

            // Only attempt to replace master if master value is passed
            // If master value is not passed, the default is "salt"
            if (csv_multimasters != "salt") {
                // Let's see if we have multiple masters
                char[] separators = new char[] { ',', ' ' };
                string[] multimasters = csv_multimasters.Split(separators, StringSplitOptions.RemoveEmptyEntries);
                string masters = string.Join(Environment.NewLine, multimasters);
                string master_value = "";
                if (multimasters.Length > 1) {
                    // Multimaster
                    master_value = "master:";
                    foreach (string master in multimasters) {
                        master_value += Environment.NewLine + "- " + master;
                    }
                    master_value = master_value.Trim() + Environment.NewLine;
                } else {
                    // Single Master
                    master_value = "master: " + masters.Trim() + Environment.NewLine;
                }
                session.Log("...New Master Value: {0}", master_value);

                bool master_emitted = false;

                // Single master entry
                Regex regx_single_master = new Regex(@"(^master:[ \t]+\S+\r?\n?)", RegexOptions.Multiline);
                // Search config using single master matcher
                session.Log("...Searching for single_master");
                session.Log(config_content);
                MatchCollection master_matches = regx_single_master.Matches(config_content);
                // If one is found, replace with the new master value and done
                if (master_matches.Count == 1) {
                    session.Log("......Found single master, setting new master value");
                    config_content = regx_single_master.Replace(config_content, master_value);
                    master_emitted = true;
                } else if (master_matches.Count > 1) {
                    session.Log("......ERROR Found multiple matches for single master");
                }

                if (!master_emitted) {
                    // Multimaster entry
                    Regex regx_multi_master = new Regex(@"(^master: *(?:\r?\n?- +.*\r?\n?)+\r?\n?)", RegexOptions.Multiline);
                    // Search config using multi master matcher
                    session.Log("...Searching for multi master");
                    master_matches = regx_multi_master.Matches(config_content);
                    // If one is found, replace with the new master value and done
                    if (master_matches.Count == 1) {
                        session.Log("......Found multi master, setting new master value");
                        config_content = regx_multi_master.Replace(config_content, master_value);
                        master_emitted = true;
                    } else if (master_matches.Count > 1) {
                        session.Log("......ERROR Found multiple matches for multi master");
                    }
                }

                if (!master_emitted) {
                    // Commented master entry
                    Regex regx_commented_master = new Regex(@"(^# *master: *\S+\r?\n?)", RegexOptions.Multiline);
                    // Search config using commented master matcher
                    session.Log("...Searching for commented master");
                    master_matches = regx_commented_master.Matches(config_content);
                    // If one is found, replace with the new master value and done
                    if (master_matches.Count == 1) {
                        session.Log("......Found commented master, setting new master value");
                        // This one's a little different, we want to keep the comment
                        // and add the new master on the next line
                        config_content = regx_commented_master.Replace(config_content, "$1" + master_value);
                        master_emitted = true;
                    } else if (master_matches.Count > 1) {
                        session.Log("......ERROR Found multiple matches for single master");
                    }
                }

                if (!master_emitted) {
                    // Commented multi master entry
                    Regex regx_commented_multi_master = new Regex(@"(^# *master: *(?:\r?\n?# *- +.+\r?\n?)+)", RegexOptions.Multiline);
                    // Search config using commented multi master matcher
                    session.Log("...Searching for commented multi master");
                    master_matches = regx_commented_multi_master.Matches(config_content);
                    // If one is found, replace with the new master value and done
                    if (master_matches.Count == 1) {
                        session.Log("......Found commented multi master, setting new master value");
                        // This one's a little different, we want to keep the comment
                        // and add the new master on the next line
                        config_content = regx_commented_multi_master.Replace(config_content, "$1" + master_value);
                        master_emitted = true;
                    } else if (master_matches.Count > 1) {
                        session.Log("......ERROR Found multiple matches for single master");
                    }
                }
                if (!master_emitted) {
                    session.Log("......No master found in config, appending master");
                    config_content = config_content + master_value;
                    master_emitted = true;
                }
            }

            // Only attempt to replace the minion id if a minion id is passed
            // If the minion id is not passed, the default is "hostname"
            if (id != "hostname") {

                string id_value = "id: " + id + Environment.NewLine;
                bool id_emitted = false;

                // id entry
                Regex regx_id = new Regex(@"(^id:[ \t]+\S+\r?\n?)", RegexOptions.Multiline);
                // Search config using id matcher
                session.Log("...Searching for id");
                MatchCollection id_matches = regx_id.Matches(config_content);
                // If one is found, replace with the new id value and done
                if (id_matches.Count == 1) {
                    session.Log("......Found id, setting new id value");
                    config_content = regx_id.Replace(config_content, id_value);
                    id_emitted = true;
                } else if (id_matches.Count > 1) {
                    session.Log("......ERROR Found multiple matches for id");
                }

                if (!id_emitted) {
                    // commented id entry
                    Regex regx_commented_id = new Regex(@"(^# *id: *\S+\r?\n?)", RegexOptions.Multiline);
                    // Search config using commented id matcher
                    session.Log("...Searching for commented id");
                    id_matches = regx_commented_id.Matches(config_content);
                    // If one is found, replace with the new id value and done
                    if (id_matches.Count == 1) {
                        session.Log("......Found commented id, setting new id value");
                        config_content = regx_commented_id.Replace(config_content, "$1" + id_value);
                        id_emitted = true;
                    } else if (id_matches.Count > 1) {
                        session.Log("......ERROR Found multiple matches for commented id");
                    }
                }

                if (!id_emitted) {
                    // commented id entry
                    Regex regx_commented_id_empty = new Regex(@"(^# *id: *\r?\n?)", RegexOptions.Multiline);
                    // Search config using commented id matcher
                    session.Log("...Searching for commented id");
                    id_matches = regx_commented_id_empty.Matches(config_content);
                    // If one is found, replace with the new id value and done
                    if (id_matches.Count == 1) {
                        session.Log("......Found commented id, setting new id value");
                        config_content = regx_commented_id_empty.Replace(config_content, "$1" + id_value);
                        id_emitted = true;
                    } else if (id_matches.Count > 1) {
                        session.Log("......ERROR Found multiple matches for commented id");
                    }
                }
                if (!id_emitted) {
                    session.Log("......No minion ID found in config, appending minion ID");
                    config_content = config_content + id_value;
                    id_emitted = true;
                }
            }
            session.Log("...Writing config content to: {0}", config_file);
            File.WriteAllText(config_file, config_content);

            session.Log("...END write_master_and_id_to_file_DECAC");
        }


        private static void read_master_and_id_from_file_IMCAC(Session session, String configfile, ref String ref_master, ref String ref_id) {
            /* How to match multimasters *
                match `master: `MASTER*:
                if MASTER:
                  master = MASTER
                else, a list of masters may follow:
                  while match `- ` MASTER:
                    master += MASTER
            */
            if (configfile.Length == 0) {
                session.Log("...configfile not passed");
                return;
            }
            if (!File.Exists(configfile)) {
                session.Log("...configfile does not exist: " + configfile);
                return;
            }
            session.Log("...searching master and id in " + configfile);
            bool configExists = File.Exists(configfile);
            session.Log("......file exists " + configExists);
            if (!configExists) { return; }
            string[] configLines = File.ReadAllLines(configfile);
            Regex line_key_maybe_value = new Regex(@"^([a-zA-Z_]+):\s*([0-9a-zA-Z_.-]*)\s*$");
            Regex line_listvalue = new Regex(@"^\s*-\s*(.*)$");
            bool look_for_keys_otherwise_look_for_multimasters = true;
            List<string> multimasters = new List<string>();
            foreach (string line in configLines) {
                if (look_for_keys_otherwise_look_for_multimasters && line_key_maybe_value.IsMatch(line)) {
                    Match m = line_key_maybe_value.Match(line);
                    string key = m.Groups[1].ToString();
                    string maybe_value = m.Groups[2].ToString();
                    //session.Log("...ANY KEY " + key + " " + maybe_value);
                    if (key == "master") {
                        if (maybe_value.Length > 0) {
                            ref_master = maybe_value;
                            session.Log("......master " + ref_master);
                        } else {
                            session.Log("...... now searching multimasters");
                            look_for_keys_otherwise_look_for_multimasters = false;
                        }
                    }
                    if (key == "id" && maybe_value.Length > 0) {
                        ref_id = maybe_value;
                        session.Log("......id " + ref_id);
                    }
                } else if (line_listvalue.IsMatch(line)) {
                    Match m = line_listvalue.Match(line);
                    multimasters.Add(m.Groups[1].ToString());
                } else {
                    look_for_keys_otherwise_look_for_multimasters = true;
                }
            }
            if (multimasters.Count > 0) {
                ref_master = string.Join(",", multimasters.ToArray());
                session.Log("......master " + ref_master);
            }
        }


        [CustomAction]
        public static void stop_service(Session session, string a_service) {
            // the installer cannot assess the log file unless it is released.
            session.Log("...stop_service " + a_service);
            ServiceController service = new ServiceController(a_service);
            service.Stop();
            var timeout = new TimeSpan(0, 0, 1); // seconds
            service.WaitForStatus(ServiceControllerStatus.Stopped, timeout);
        }


        [CustomAction]
        public static ActionResult kill_python_exe(Session session) {
            // because a running process can prevent removal of files
            // Get full path and command line from running process
            // see https://github.com/saltstack/salt/issues/42862
            session.Log("...BEGIN kill_python_exe (CustomAction01.cs)");
            using (
                var wmi_searcher = new ManagementObjectSearcher(
                    "SELECT ProcessID, ExecutablePath, CommandLine FROM Win32_Process WHERE CommandLine LIKE '%salt-minion%' AND NOT CommandLine LIKE '%msiexec%'"
                )
            ) {
                foreach (ManagementObject wmi_obj in wmi_searcher.Get()) {
                    String ProcessID = wmi_obj["ProcessID"].ToString();
                    Int32 pid = Int32.Parse(ProcessID);
                    String ExecutablePath = wmi_obj["ExecutablePath"].ToString();
                    String CommandLine = wmi_obj["CommandLine"].ToString();
                    session.Log("...kill_python_exe " + ExecutablePath + " " + CommandLine);
                    Process proc11 = Process.GetProcessById(pid);
                    try {
                        proc11.Kill();
                    } catch (Exception exc) {
                        session.Log("...kill_python_exe " + ExecutablePath + " " + CommandLine);
                        session.Log(exc.ToString());
                        // ignore wmiresults without these properties
                    }
                }
            }
            session.Log("...END kill_python_exe");
            return ActionResult.Success;
        }

        [CustomAction]
        public static ActionResult del_NSIS_DECAC(Session session) {
            // Leaves the Config
            /*
             * If NSIS is installed:
             *   remove salt-minion service,
             *   remove registry
             *   remove files, except /salt/conf and /salt/var
             *
             *   The msi cannot use uninst.exe because the service would no longer start.
            */
            session.Log("...BEGIN del_NSIS_DECAC");
            RegistryKey HKLM = Registry.LocalMachine;

            string ARPstring = @"Microsoft\Windows\CurrentVersion\Uninstall\Salt Minion";
            RegistryKey ARPreg = cutil.get_registry_SOFTWARE_key(session, ARPstring);
            string uninstexe = "";
            if (ARPreg != null) uninstexe = ARPreg.GetValue("UninstallString").ToString();
            session.Log("from REGISTRY uninstexe = " + uninstexe);

            string SOFTWAREstring = @"Salt Project\Salt";
            RegistryKey SOFTWAREreg = cutil.get_registry_SOFTWARE_key(session, SOFTWAREstring);
            var bin_dir = "";
            if (SOFTWAREreg != null) bin_dir = SOFTWAREreg.GetValue("bin_dir").ToString();
            session.Log("from REGISTRY bin_dir = " + bin_dir);
            if (bin_dir == "") bin_dir = @"C:\salt\bin";
            session.Log("bin_dir = " + bin_dir);

            session.Log("Going to stop service salt-minion ...");
            cutil.shellout(session, "sc stop salt-minion");

            session.Log("Going to delete service salt-minion ...");
            cutil.shellout(session, "sc delete salt-minion");

            session.Log("Going to kill ...");
            kill_python_exe(session);

            session.Log("Going to delete ARP registry entry ...");
            cutil.del_registry_SOFTWARE_key(session, ARPstring);

            session.Log("Going to delete SOFTWARE registry entry ...");
            cutil.del_registry_SOFTWARE_key(session, SOFTWAREstring);

            session.Log("Going to delete uninst.exe ...");
            cutil.del_file(session, uninstexe);

            // This deletes any file that starts with "salt" from the install_dir
            var bindirparent = Path.GetDirectoryName(bin_dir);
            session.Log(@"Going to delete bindir\..\salt\*.*    ...   " + bindirparent);
            if (Directory.Exists(bindirparent)){
                try { foreach (FileInfo fi in new DirectoryInfo(bindirparent).GetFiles("salt*.*")) { fi.Delete(); } } catch (Exception) {; }
            }

            // This deletes the bin directory
            session.Log("Going to delete bindir ... " + bin_dir);
            cutil.del_dir(session, bin_dir);

            session.Log("...END del_NSIS_DECAC");
            return ActionResult.Success;
        }


        [CustomAction]
        public static ActionResult WriteConfig_DECAC(Session session) {
            /*
             * This function must leave the config files according to the CONFIG_TYPE's 1-3
             * This function is deferred (_DECAC)
             * This function runs after the msi has created the c:\salt\conf\minion file, which is a comment-only text.
             * If there was a previous install, there could be many config files.
             * The previous install c:\salt\conf\minion file could contain non-comments.
             * One of the non-comments could be master.
             * It could be that this installer has a different master.
             *
             */
            // Must have this signature or cannot uninstall not even write to the log
            session.Log("...BEGIN WriteConfig_DECAC");
            // Get msi properties
            string master = cutil.get_property_DECAC(session, "master");;
            string id = cutil.get_property_DECAC(session, "id");;
            string config_type = cutil.get_property_DECAC(session, "config_type");
            string MINION_CONFIG = cutil.get_property_DECAC(session, "MINION_CONFIG");
            string CONFDIR = cutil.get_property_DECAC(session, "CONFDIR");
            string MINION_CONFIGFILE = Path.Combine(CONFDIR, "minion");
            session.Log("...MINION_CONFIGFILE {0}", MINION_CONFIGFILE);
            bool file_exists = File.Exists(MINION_CONFIGFILE);
            session.Log("...file exists {0}", file_exists);

            // Get environment variables
            string ProgramData = System.Environment.GetEnvironmentVariable("ProgramData");

            if (MINION_CONFIG.Length > 0) {
                session.Log("...Found MINION_CONFIG: {0}", MINION_CONFIG);
                apply_minion_config_DECAC(session, MINION_CONFIG);  // A single msi property is written to file
                session.Log("...END WriteConfig_DECAC");
                return ActionResult.Success;
            }
            switch (config_type) {
                case "Existing":
                    session.Log("...CONFIG_TYPE: Existing, no changes will be made");
                    return ActionResult.Success;
                case "Custom":
                    // copy custom file before updating master and minion id
                    session.Log("...CONFIG_TYPE: Custom, copying custom config");
                    save_custom_config_file_DECAC(session);
                    break;
                case "Default":
                    // This is just a placeholder for CONFIG_TYPE=Default
                    session.Log("...CONFIG_TYPE: Default, using default config");
                    break;
                default:
                    session.Log("...UNKNOWN CONFIG_TYPE: " + config_type);
                    // Not sure if this is a valid ActionResult, but we need to die here
                    return ActionResult.Failure;
            }

            write_master_and_id_to_file_DECAC(session, MINION_CONFIGFILE, master, id); // Two msi properties are replaced inside files
            session.Log("...END WriteConfig_DECAC");
            return ActionResult.Success;
        }


        [CustomAction]
        public static ActionResult MoveInsecureConfig_DECAC(Session session) {
            // This appends .insecure-yyyy-MM-ddTHH-mm-ss to an insecure config directory
            // C:\salt\conf.insecure-2021-10-01T12-23-32
            // Only called when INSECURE_CONFIG_FOUND is set to an insecure minion config dir
            session.Log("...BEGIN MoveInsecureConf_DECAC");

            string minion_config_dir = cutil.get_property_DECAC(session, "INSECURE_CONFIG_FOUND");
            string timestamp_bak = ".insecure-" + DateTime.Now.ToString("yyyy-MM-ddTHH-mm-ss");
            cutil.Move_dir(session, minion_config_dir, timestamp_bak);

            session.Log("...END MoveInsecureConf_DECAC");

            return ActionResult.Success;
        }

        private static void save_custom_config_file_DECAC(Session session) {
            session.Log("...BEGIN save_custom_config_file_DECAC");
            string custom_config = cutil.get_property_DECAC(session, "custom_config");
            string CONFDIR       = cutil.get_property_DECAC(session, "CONFDIR");

            // Make sure a CUSTOM_CONFIG file has been passed
            if (!(custom_config.Length > 0 )) {
                session.Log("...CUSTOM_CONFIG not passed");
                return;
            }

            // Make sure the CUSTOM_CONFIG file exists
            // Try as passed
            if (File.Exists(custom_config)) {
                session.Log("...found full path to CUSTOM_CONFIG: " + custom_config);
            } else {
                // try relative path
                session.Log("...no CUSTOM_CONFIG: " + custom_config);
                session.Log("...Try relative path");
                string directory_of_the_msi = cutil.get_property_DECAC(session, "sourcedir");
                custom_config = Path.Combine(directory_of_the_msi, custom_config);
                if (File.Exists(custom_config)) {
                    session.Log("...found relative path to CUSTOM_CONFIG: " + custom_config);
                } else {
                    // CUSTOM_CONFIG not found
                    session.Log("...CUSTOM_CONFIG not found: " + custom_config);
                    return;
                }
            }
            // Copy the custom config (passed via the CLI, for now)
            if (!File.Exists(CONFDIR)) {
                session.Log("...Creating CONFDIR: " + CONFDIR);
                Directory.CreateDirectory(CONFDIR);
            }
            File.Copy(custom_config, Path.Combine(CONFDIR, "minion"), true);
            session.Log("...END save_custom_config_file_DECAC");
        }

        [CustomAction]
        public static ActionResult DeleteConfig_DECAC(Session session) {
            // This removes not only config, but ROOTDIR or subfolders of ROOTDIR, depending on properties CLEAN_INSTALL and REMOVE_CONFIG
            // Called on install, upgrade and uninstall
            session.Log("...BEGIN DeleteConfig_DECAC");

            // Determine wether to delete everything and DIRS
            string CLEAN_INSTALL = cutil.get_property_DECAC(session, "CLEAN_INSTALL");
            string REMOVE_CONFIG = cutil.get_property_DECAC(session, "REMOVE_CONFIG");
            string INSTALLDIR    = cutil.get_property_DECAC(session, "INSTALLDIR");
            string bindir        = Path.Combine(INSTALLDIR, "bin");
            string ROOTDIR       = cutil.get_property_DECAC(session, "ROOTDIR");
            string ProgramData   = System.Environment.GetEnvironmentVariable("ProgramData");
            string ROOTDIR_old   = @"C:\salt";
            string ROOTDIR_new   =  Path.Combine(ProgramData, @"Salt Project\Salt");
            // The registry subkey deletes itself

            if (CLEAN_INSTALL.Length > 0) {
                session.Log("...CLEAN_INSTALL -- remove both old and new root_dirs");
                cutil.del_dir(session, ROOTDIR_old);
                cutil.del_dir(session, ROOTDIR_new);
            }

            session.Log("...deleting bindir (msi only deletes what it installed, not *.pyc)  = " + bindir);
            cutil.del_dir(session, bindir);

            if (REMOVE_CONFIG.Length > 0) {
                session.Log("...REMOVE_CONFIG -- remove the current root_dir");
                cutil.del_dir(session, ROOTDIR);
            } else {
                session.Log("...Not REMOVE_CONFIG -- remove var and srv from the current root_dir");
                cutil.del_dir(session, ROOTDIR, "var");
                cutil.del_dir(session, ROOTDIR, "srv");
            }

            session.Log("...END DeleteConfig_DECAC");
            return ActionResult.Success;
        }


        [CustomAction]
        public static ActionResult MoveConfig_DECAC(Session session) {
            // This moves the root_dir from the old location (C:\salt) to the
            // new location (%ProgramData%\Salt Project\Salt)
            session.Log("...BEGIN MoveConfig_DECAC");

            // Get %ProgramData%
            string ProgramData   = System.Environment.GetEnvironmentVariable("ProgramData");

            string RootDirOld = @"C:\salt";
            string RootDirNew = Path.Combine(ProgramData, @"Salt Project\Salt");
            string RootDirNewParent = Path.Combine(ProgramData, @"Salt Project");

            session.Log("...RootDirOld       " + RootDirOld + " exists: " + Directory.Exists(RootDirOld));
            session.Log("...RootDirNew       " + RootDirNew + " exists: " + Directory.Exists(RootDirNew));
            session.Log("...RootDirNewParent " + RootDirNewParent + " exists: " + Directory.Exists(RootDirNewParent));

            // Create parent dir if it doesn't exist
            if (! Directory.Exists(RootDirNewParent)) {
                Directory.CreateDirectory(RootDirNewParent);
            }

            // Requires that the parent directory exists
            // Requires that the NewDir does NOT exist
            Directory.Move(RootDirOld, RootDirNew);

            session.Log("...END MoveConfig_DECAC");
            return ActionResult.Success;
        }


        private static void apply_minion_config_DECAC(Session session, string MINION_CONFIG) {
            // Precondition: parameter MINION_CONFIG contains the content of the MINION_CONFIG property and is not empty
            // Remove all other config
            session.Log("...apply_minion_config_DECAC BEGIN");
            string CONFDIR      = cutil.get_property_DECAC(session, "CONFDIR");
            string MINION_D_DIR = Path.Combine(CONFDIR, "minion.d");
            // Write conf/minion
            string lines = MINION_CONFIG.Replace("^", Environment.NewLine);
            cutil.Writeln_file(session, CONFDIR, "minion", lines);
            // Remove conf/minion_id
            string minion_id = Path.Combine(CONFDIR, "minion_id");
            session.Log("...searching " + minion_id);
            if (File.Exists(minion_id)) {
                File.Delete(minion_id);
                session.Log("...deleted   " + minion_id);
            }
            // Remove conf/minion.d/*.conf
            session.Log("...searching *.conf in " + MINION_D_DIR);
            if (Directory.Exists(MINION_D_DIR)) {
                var conf_files = System.IO.Directory.GetFiles(MINION_D_DIR, "*.conf");
                foreach (var conf_file in conf_files) {
                    File.Delete(conf_file);
                    session.Log("...deleted   " + conf_file);
                }
            }
            session.Log(@"...apply_minion_config_DECAC END");
        }



        [CustomAction]
        public static ActionResult  BackupConfig_DECAC(Session session) {
            session.Log("...BackupConfig_DECAC BEGIN");
            string timestamp_bak = "-" + DateTime.Now.ToString("yyyy-MM-ddTHH-mm-ss") + ".bak";
            session.Log("...timestamp_bak = " + timestamp_bak);
            cutil.Move_file(session, @"C:\salt\conf\minion", timestamp_bak);
            cutil.Move_file(session, @"C:\salt\conf\minion_id", timestamp_bak);
            cutil.Move_dir(session, @"C:\salt\conf\minion.d", timestamp_bak);
            session.Log("...BackupConfig_DECAC END");

            return ActionResult.Success;
        }
    }
}
