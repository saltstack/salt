using Microsoft.Deployment.WindowsInstaller;
using Microsoft.Tools.WindowsInstallerXml;
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


        // Process image names kill_python_exe may terminate (interactive shells, not only service).
        private static readonly string[] kill_python_exe_allowlist = new string[] {
            "salt-minion.exe", "salt-call.exe", "salt-cp.exe", "ssm.exe"
        };

        private static bool kill_python_exe_ProcessNameMatchesAllowlist(string wmiName, string executablePath) {
            if (!string.IsNullOrEmpty(wmiName)) {
                foreach (string exe in kill_python_exe_allowlist) {
                    if (string.Compare(wmiName, exe, StringComparison.OrdinalIgnoreCase) == 0)
                        return true;
                }
            }
            if (!string.IsNullOrEmpty(executablePath)) {
                string fn = Path.GetFileName(executablePath);
                foreach (string exe in kill_python_exe_allowlist) {
                    if (string.Compare(fn, exe, StringComparison.OrdinalIgnoreCase) == 0)
                        return true;
                }
            }
            return false;
        }

        // CustomActionData / NSIS UninstallString: "C:\...\uninst.exe" or C:\...\uninst.exe /S
        // Do not split unquoted paths on the first space (breaks "C:\Program Files\...\uninst.exe").
        private static string remove_NSIS_ParseUninstExePath(Session session, string raw) {
            if (string.IsNullOrEmpty(raw)) return "";
            string s = raw.Trim();
            string exePath = "";
            if (s.Length > 0 && s[0] == '"') {
                int end = s.IndexOf('"', 1);
                if (end > 1) exePath = s.Substring(1, end - 1);
            } else {
                int u = s.IndexOf("uninst.exe", StringComparison.OrdinalIgnoreCase);
                if (u >= 0)
                    exePath = s.Substring(0, u + "uninst.exe".Length);
                else {
                    int sp = s.IndexOf(' ');
                    exePath = sp > 0 ? s.Substring(0, sp) : s;
                }
            }
            exePath = (exePath ?? "").Trim();
            if (exePath.Length > 0)
                session.Log("...remove_NSIS_ParseUninstExePath -> " + exePath);
            return exePath;
        }

        // NSIS temp uninstall child: short name like Un_xxxxx.exe (not uninst.exe). Tie to this install via CommandLine/ExecutablePath.
        private static bool remove_NSIS_IsNsisTempUninstallerProcess(string name, string commandLine, string executablePath, string instRoot) {
            if (string.IsNullOrEmpty(name)) return false;
            string fn = name.Trim();
            if (fn.IndexOf("uninst.exe", StringComparison.OrdinalIgnoreCase) >= 0) return false;
            if (!fn.StartsWith("Un", StringComparison.OrdinalIgnoreCase)) return false;
            string cl = commandLine ?? "";
            string ep = executablePath ?? "";
            if (cl.IndexOf(instRoot, StringComparison.OrdinalIgnoreCase) >= 0) return true;
            if (ep.IndexOf(instRoot, StringComparison.OrdinalIgnoreCase) >= 0) return true;
            if (cl.IndexOf("Salt Project", StringComparison.OrdinalIgnoreCase) >= 0) return true;
            if (cl.IndexOf("NSIS", StringComparison.OrdinalIgnoreCase) >= 0) return true;
            return false;
        }

        private static int remove_NSIS_CountNsisTempUninstallerChildren(Session session, string instRoot) {
            int n = 0;
            try {
                string wmi = "SELECT ProcessId, Name, ExecutablePath, CommandLine FROM Win32_Process WHERE Name LIKE 'Un%' OR Name LIKE 'un%'";
                using (ManagementObjectSearcher searcher = new ManagementObjectSearcher(wmi)) {
                    foreach (ManagementObject o in searcher.Get()) {
                        try {
                            if (o["ProcessId"] == null) continue;
                            int pid = int.Parse(o["ProcessId"].ToString());
                            if (pid == Process.GetCurrentProcess().Id) continue;
                            string nm = o["Name"] != null ? o["Name"].ToString() : "";
                            string cl = o["CommandLine"] != null ? o["CommandLine"].ToString() : "";
                            string ep = o["ExecutablePath"] != null ? o["ExecutablePath"].ToString() : "";
                            if (!remove_NSIS_IsNsisTempUninstallerProcess(nm, cl, ep, instRoot)) continue;
                            n++;
                        } catch (Exception ex) {
                            session.Log("...remove_NSIS_CountNsisTempUninstallerChildren row: " + ex.Message);
                        }
                    }
                }
            } catch (Exception ex) {
                session.Log("...remove_NSIS_CountNsisTempUninstallerChildren: " + ex.Message);
            }
            return n;
        }

        // After uninst.exe stub exits, wait until NSIS removes ssm.exe (Salt-Minion-Setup.nsi deletes it before uninst.exe).
        // INSTDIR folder often remains; ssm.exe is a reliable completion marker. WMI Un* count is for logging only.
        private static bool remove_NSIS_WaitForNsisUninstallComplete(Session session, string instRoot, int maxWaitSeconds) {
            if (string.IsNullOrEmpty(instRoot)) return false;
            string ssmPath = Path.Combine(instRoot, "ssm.exe");
            int intervalMs = 2000;
            int maxMs = maxWaitSeconds * 1000;
            int elapsed = 0;
            int lastLogChild = -1;
            while (elapsed < maxMs) {
                bool ssmGone = false;
                try {
                    ssmGone = !File.Exists(ssmPath);
                } catch (Exception ex) {
                    session.Log("...remove_NSIS_WaitForNsisUninstallComplete: " + ex.Message);
                    return false;
                }
                int nChild = remove_NSIS_CountNsisTempUninstallerChildren(session, instRoot);
                if (ssmGone) {
                    session.Log("...remove_NSIS_WaitForNsisUninstallComplete: ssm.exe gone after " + (elapsed / 1000) + "s (nsisUnChildCount=" + nChild + ")");
                    return true;
                }
                if (elapsed == 0 || elapsed % 30000 == 0 || nChild != lastLogChild) {
                    session.Log("...remove_NSIS_WaitForNsisUninstallComplete: elapsed=" + (elapsed / 1000) + "s ssmGone=" + ssmGone + " nsisUnChildCount=" + nChild);
                    lastLogChild = nChild;
                }
                System.Threading.Thread.Sleep(intervalMs);
                elapsed += intervalMs;
            }
            session.Log("...remove_NSIS_WaitForNsisUninstallComplete: timeout after " + maxWaitSeconds + "s");
            return false;
        }

        [CustomAction]
        public static ActionResult kill_python_exe(Session session) {
            // because a running process can prevent removal of files
            // Get full path and command line from running process
            // see https://github.com/saltstack/salt/issues/42862
            session.Log("...BEGIN kill_python_exe (CustomAction01.cs)");

            // Give the minion enough time to finish its internal stop_async (graceful shutdown).
            // salt/minion.py:MinionManager.stop_async has a static 5-second sleep to allow
            // the I/O loop to process and send any remaining "return" messages to the Master.
            // We wait 6 seconds here to ensure that we don't aggressively kill the process
            // while it is still performing its legitimate cleanup. After this window,
            // we proceed to kill any lingering or orphan processes that would otherwise
            // lock DLLs (like pywin32 or cryptography) and cause a "Frankenstein" installation.
            session.Log("...Waiting 6 seconds for graceful shutdown...");
            System.Threading.Thread.Sleep(6000);

            try {
                string installDir = cutil.get_property_IMCAC(session, "INSTALLDIR");
                session.Log("...INSTALLDIR (informational): " + installDir);
            } catch (Exception) {
                session.Log("...INSTALLDIR not available for logging (non-fatal).");
            }

            // Match only explicit Salt worker images by Win32_Process.Name. Do not use
            // CommandLine LIKE '%salt-minion%' — it false-positives on Salt-Minion-Setup.exe
            // (case-insensitive substring) and can kill the NSIS parent while msiexec uninstall runs.
            session.Log("...Allowlisted images: salt-minion.exe, salt-call.exe, salt-cp.exe, ssm.exe");

            // Perform multiple passes to ensure stubborn or child processes are caught
            for (int attempt = 1; attempt <= 3; attempt++) {
                session.Log("...Kill attempt " + attempt + " of 3");
                int killedCount = 0;
                foreach (string imageExe in kill_python_exe_allowlist) {
                    string safeImage = imageExe.Replace("'", "''");
                    string wmi_query = "SELECT ProcessID, ExecutablePath, CommandLine, Name FROM Win32_Process WHERE Name = '" + safeImage + "'";
                    using (var wmi_searcher = new ManagementObjectSearcher(wmi_query)) {
                        foreach (ManagementObject wmi_obj in wmi_searcher.Get()) {
                            try {
                                if (wmi_obj["ProcessID"] == null) continue;
                                String ProcessID = wmi_obj["ProcessID"].ToString();
                                Int32 pid = Int32.Parse(ProcessID);

                                // Don't kill ourselves or the installer
                                if (pid == Process.GetCurrentProcess().Id) continue;

                                string commandLine = wmi_obj["CommandLine"] != null ? wmi_obj["CommandLine"].ToString() : "";
                                if (commandLine.IndexOf("msiexec", StringComparison.OrdinalIgnoreCase) >= 0) {
                                    session.Log("...skipping PID=" + ProcessID + " (msiexec in command line)");
                                    continue;
                                }

                                string wmiName = wmi_obj["Name"] != null ? wmi_obj["Name"].ToString() : "";
                                string executablePath = wmi_obj["ExecutablePath"] != null ? wmi_obj["ExecutablePath"].ToString() : "";
                                if (!kill_python_exe_ProcessNameMatchesAllowlist(wmiName, executablePath)) {
                                    session.Log("...skipping PID=" + ProcessID + " (not allowlisted image)");
                                    continue;
                                }

                                session.Log("...killing process: PID=" + ProcessID + " Name=" + wmiName + " Path=" + (executablePath.Length > 0 ? executablePath : "Unknown"));
                                Process proc = Process.GetProcessById(pid);
                                proc.Kill();
                                killedCount++;
                            } catch (Exception exc) {
                                session.Log("...failed to kill process: " + exc.Message);
                            }
                        }
                    }
                }
                if (killedCount == 0) {
                    session.Log("...No matching processes found to kill.");
                    break;
                }
                if (attempt < 3) {
                    session.Log("...Waiting 2 seconds before next kill attempt...");
                    System.Threading.Thread.Sleep(2000);
                }
            }
            session.Log("...END kill_python_exe");
            return ActionResult.Success;
        }

        [CustomAction]
        public static ActionResult remove_NSIS_IMCAC(Session session) {
            /*
             * NSIS->MSI: remove_NSIS_IMCAC — immediate C# CA (Execute=immediate; _IMCAC, not deferred _DECAC/CADH).
             * Run NSIS silent uninstall before InstallValidate (sequenced in Product.wxs).
             * WiX sets NSIS_UNINSTALLSTRING from ARP UninstallString (Win64=yes finds native 64-bit key).
             * Immediate CA can read that property; deferred CAs would run at InstallFinalize (too late).
             *
             * Launch the real uninst.exe with /S only (no temp copy; NSIS infers INSTDIR from the exe path). The stub often exits while a temp
             * child (Un*.exe) continues; poll until ssm.exe under INSTDIR is gone (NSIS deletes it; folder may remain). WMI counts matching Un*
             * processes for logging and stall visibility (bounded wait, 600s).
             * NSIS uninstallSalt removes the salt-minion service; the MSI install then registers the service again.
             */
            session.Log("...BEGIN remove_NSIS_IMCAC");
            try {
                string rawLine = "";
                try {
                    rawLine = session["CustomActionData"];
                } catch (Exception) { }
                if (string.IsNullOrEmpty(rawLine)) {
                    try {
                        rawLine = session["NSIS_UNINSTALLSTRING"] ?? "";
                    } catch (Exception ex) {
                        session.Log("...remove_NSIS_IMCAC: NSIS_UNINSTALLSTRING: " + ex.Message);
                    }
                }
                string sourceUninst = remove_NSIS_ParseUninstExePath(session, rawLine);
                if (sourceUninst.Length == 0 || !File.Exists(sourceUninst)) {
                    session.Log("...remove_NSIS_IMCAC: missing or absent NSIS uninstaller: " + sourceUninst);
                    return ActionResult.Failure;
                }
                string instRoot = Path.GetDirectoryName(sourceUninst);
                if (string.IsNullOrEmpty(instRoot)) {
                    session.Log("...remove_NSIS_IMCAC: could not derive INSTDIR from " + sourceUninst);
                    return ActionResult.Failure;
                }
                instRoot = instRoot.TrimEnd('\\', '/');
                session.Log("...remove_NSIS_IMCAC: NSIS INSTDIR = " + instRoot);

                ProcessStartInfo psi = new ProcessStartInfo();
                psi.FileName = sourceUninst;
                psi.Arguments = "/S";
                psi.UseShellExecute = false;
                psi.WindowStyle = ProcessWindowStyle.Hidden;
                session.Log("...remove_NSIS_IMCAC: Process.Start FileName=" + sourceUninst + " Arguments=/S");
                using (Process p = Process.Start(psi)) {
                    if (p == null) {
                        session.Log("...remove_NSIS_IMCAC: Process.Start returned null");
                        return ActionResult.Failure;
                    }
                    p.WaitForExit();
                    int code = p.ExitCode;
                    session.Log("...remove_NSIS_IMCAC: uninst.exe stub exit code = " + code);
                    if (code != 0)
                        return ActionResult.Failure;
                }
                if (!remove_NSIS_WaitForNsisUninstallComplete(session, instRoot, 600)) {
                    session.Log("...remove_NSIS_IMCAC: uninstall did not complete within timeout (ssm.exe still present)");
                    return ActionResult.Failure;
                }
            } catch (Exception ex) {
                session.Log("...remove_NSIS_IMCAC: " + ex.Message);
                return ActionResult.Failure;
            }
            session.Log("...END remove_NSIS_IMCAC");
            return ActionResult.Success;
        }

        [CustomAction]
        public static ActionResult clear_python_caches_IMCAC(Session session) {
            /*
             * Remove __pycache__ trees, stray *.pyc, and empty dirs left under [INSTALLDIR]
             * before InstallFiles (upgrade/fresh/repair). Sequenced after kill_python_exe.
             * Does not run on REMOVE=ALL. Full uninstall and DeleteConfig2 (CLEAN_INSTALL)
             * still clear bytecode via clear_python_bytecode_caches_under_dir at the start
             * of DeleteConfig_DECAC (same helper; see Product.wxs / Product-README).
             */
            session.Log("...BEGIN clear_python_caches_IMCAC");
            try {
                string installDir = "";
                try {
                    installDir = cutil.get_property_IMCAC(session, "INSTALLDIR");
                } catch (Exception ex) {
                    session.Log("...clear_python_caches_IMCAC: INSTALLDIR: " + ex.Message);
                }
                if (installDir == null) installDir = "";
                installDir = installDir.Trim();
                if (installDir.Length > 0)
                    cutil.clear_python_bytecode_caches_under_dir(session, installDir);
            } catch (Exception ex) {
                session.Log("...clear_python_caches_IMCAC: " + ex.Message);
            }
            session.Log("...END clear_python_caches_IMCAC");
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
            // Deferred cleanup: WiX schedules this entry as DeleteConfig_DECAC (REMOVE~=ALL)
            // and as DeleteConfig2_DECAC (CLEAN_INSTALL / upgrade path). Clears Python
            // bytecode under INSTALLDIR first, then Scripts/bin and ROOTDIR per CLEAN_INSTALL / REMOVE_CONFIG.
            session.Log("...BEGIN DeleteConfig_DECAC");

            // Determine wether to delete everything and DIRS
            string CLEAN_INSTALL = cutil.get_property_DECAC(session, "CLEAN_INSTALL");
            string REMOVE_CONFIG = cutil.get_property_DECAC(session, "REMOVE_CONFIG");
            string INSTALLDIR    = cutil.get_property_DECAC(session, "INSTALLDIR");
            string scriptsdir    = Path.Combine(INSTALLDIR, "Scripts");
            string bindir        = Path.Combine(INSTALLDIR, "bin");
            string ROOTDIR       = cutil.get_property_DECAC(session, "ROOTDIR");
            string ProgramData   = System.Environment.GetEnvironmentVariable("ProgramData");
            string ROOTDIR_old   = @"C:\salt";
            string ROOTDIR_new   =  Path.Combine(ProgramData, @"Salt Project\Salt");
            // The registry subkey deletes itself

            cutil.clear_python_bytecode_caches_under_dir(session, INSTALLDIR);

            if (CLEAN_INSTALL.Length > 0) {
                session.Log("...CLEAN_INSTALL -- remove both old and new root_dirs");
                cutil.del_dir(session, ROOTDIR_old);
                cutil.del_dir(session, ROOTDIR_new);
            }

            session.Log("...deleting Scripts dir (relenv layout) = " + scriptsdir);
            cutil.del_dir(session, scriptsdir);
            session.Log("...deleting bin dir (legacy layout) = " + bindir);
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
