using System;
using System.Collections.Generic;
using System.Text;
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

    public class Session {
        public void Log(String msg) {
            Console.WriteLine(msg);
        }
    }
    class ActionResult{
        public static ActionResult Success;
    }

    class Program {

        private static void write_master_and_id_to_file_DECAC(Session session, String configfile, string csv_multimasters, String id) {
            /* How to
             * read line
             * if line master, read multimaster, replace
             * if line id, replace
             * copy through line
            */
            char[] separators = new char[] { ',', ' ' };
            string[] multimasters = csv_multimasters.Split(separators, StringSplitOptions.RemoveEmptyEntries);

            session.Log("...want to write master and id to " + configfile);
            bool configExists = File.Exists(configfile);
            session.Log("......file exists " + configExists);
            string[] configLinesINPUT = new List<string>().ToArray();
            List<string> configLinesOUTPUT = new List<string>();
            if (configExists) {
                configLinesINPUT = File.ReadAllLines(configfile);
            }
            session.Log("...found config lines count " + configLinesINPUT.Length);
            session.Log("...got master count " + multimasters.Length);
            session.Log("...got id " + id);

            Regex line_contains_key = new Regex(@"^([a-zA-Z_]+):");
            Regex line_contains_one_multimaster = new Regex(@"^\s*-\s*([0-9a-zA-Z_.-]+)\s*$");
            bool master_emitted = false;
            bool id_emitted = false;

            bool look_for_multimasters = false;
            foreach (string line in configLinesINPUT) {
                // search master and id
                if (line_contains_key.IsMatch(line)) {
                    Match m = line_contains_key.Match(line);
                    string key = m.Groups[1].ToString();
                    if (key == "master") {
                        look_for_multimasters = true;
                        continue; // next line
                    } else if (key == "id") {
                        // emit id
                        configLinesOUTPUT.Add("id: " + id);
                        id_emitted = true;
                        continue; // next line
                    } else {
                        if (!look_for_multimasters) {
                            configLinesOUTPUT.Add(line); // copy through
                            continue; // next line
                        }
                    }
                } else {
                    if (!look_for_multimasters) {
                        configLinesOUTPUT.Add(line); // copy through
                        continue; // next line
                    }
                }

                if (look_for_multimasters) {
                    // consume multimasters
                    if (line_contains_one_multimaster.IsMatch(line)) {
                        // consume another multimaster
                    } else {
                        look_for_multimasters = false;
                        // First emit master
                        if (multimasters.Length == 1) {
                            configLinesOUTPUT.Add("master: " + multimasters[0]);
                            master_emitted = true;
                        }
                        if (multimasters.Length > 1) {
                            configLinesOUTPUT.Add("master:");
                            foreach (string onemultimaster in multimasters) {
                                configLinesOUTPUT.Add("- " + onemultimaster);
                            }
                            master_emitted = true;
                        }
                        configLinesOUTPUT.Add(line); // Then copy through whatever is not one multimaster
                    }
                }
            }

            // input is read
            if (!master_emitted) {
                // put master after hash master
                Regex line_contains_hash_master = new Regex(@"^# master:");
                List<string> configLinesOUTPUT_hash_master = new List<string>();
                foreach (string output_line in configLinesOUTPUT) {
                    configLinesOUTPUT_hash_master.Add(output_line);
                    if(line_contains_hash_master.IsMatch(output_line)) {
                        if (multimasters.Length == 1) {
                            configLinesOUTPUT_hash_master.Add("master: " + multimasters[0]);
                            master_emitted = true;
                        }
                        if (multimasters.Length > 1) {
                            configLinesOUTPUT_hash_master.Add("master:");
                            foreach (string onemultimaster in multimasters) {
                                configLinesOUTPUT_hash_master.Add("- " + onemultimaster);
                            }
                            master_emitted = true;
                        }
                    }
                }
                configLinesOUTPUT = configLinesOUTPUT_hash_master;
            }
            if (!master_emitted) {
                // put master at end
                if (multimasters.Length == 1) {
                    configLinesOUTPUT.Add("master: " + multimasters[0]);
                }
                if (multimasters.Length > 1) {
                    configLinesOUTPUT.Add("master:");
                    foreach (string onemultimaster in multimasters) {
                        configLinesOUTPUT.Add("- " + onemultimaster);
                    }
                }
            }

            if (!id_emitted) {
                // put after hash
                Regex line_contains_hash_id = new Regex(@"^# id:");
                List<string> configLinesOUTPUT_hash_id = new List<string>();
                foreach (string output_line in configLinesOUTPUT) {
                    configLinesOUTPUT_hash_id.Add(output_line);
                    if (line_contains_hash_id.IsMatch(output_line)) {
                            configLinesOUTPUT_hash_id.Add("id: " + id);
                            id_emitted = true;
                    }
                }
                configLinesOUTPUT = configLinesOUTPUT_hash_id;
            }
            if (!id_emitted) {
                // put at end
                configLinesOUTPUT.Add("id: " + id);
            }


            session.Log("...writing to " + configfile);
            string output = string.Join("\r\n", configLinesOUTPUT.ToArray()) + "\r\n";
            File.WriteAllText(configfile, output);

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
            session.Log("...searching master and id in " + configfile);
            bool configExists = File.Exists(configfile);
            session.Log("......file exists " + configExists);
            if (!configExists) { return; }
            string[] configLines = File.ReadAllLines(configfile);
            Regex line_key_maybe_value = new Regex(@"^([a-zA-Z_]+):\s*([0-9a-zA-Z_.-]*)\s*$");
            Regex line_listvalue = new Regex(@"^\s*-\s*([0-9a-zA-Z_.-]+)\s*$");
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



        public static ActionResult kill_python_exe(Session session) {
            // because a running process can prevent removal of files
            // Get full path and command line from running process
            session.Log("...BEGIN kill_python_exe");
            using (var wmi_searcher = new ManagementObjectSearcher
                ("SELECT ProcessID, ExecutablePath, CommandLine FROM Win32_Process WHERE Name = 'python.exe'")) {
                foreach (ManagementObject wmi_obj in wmi_searcher.Get()) {
                    try {
                        String ProcessID = wmi_obj["ProcessID"].ToString();
                        Int32 pid = Int32.Parse(ProcessID);
                        String ExecutablePath = wmi_obj["ExecutablePath"].ToString();
                        String CommandLine = wmi_obj["CommandLine"].ToString();
                        if (CommandLine.ToLower().Contains("salt") || ExecutablePath.ToLower().Contains("salt")) {
                            session.Log("...kill_python_exe " + ExecutablePath + " " + CommandLine);
                            Process proc11 = Process.GetProcessById(pid);
                            proc11.Kill();
                        }
                    } catch (Exception) {
                        // ignore wmiresults without these properties
                    }
                }
            }
            session.Log("...END kill_python_exe");
            return ActionResult.Success;
        }


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

            session.Log("Going to kill ...");
            kill_python_exe(session);

            session.Log("Going to stop service salt-minion ...");
            cutil.shellout(session, "sc stop salt-minion");

            session.Log("Going to delete service salt-minion ...");
            cutil.shellout(session, "sc delete salt-minion");

            session.Log("Going to delete ARP registry entry ...");
            cutil.del_registry_SOFTWARE_key(session, ARPstring);

            session.Log("Going to delete SOFTWARE registry entry ...");
            cutil.del_registry_SOFTWARE_key(session, SOFTWAREstring);

            session.Log("Going to delete bindir ... " + bin_dir);
            cutil.del_dir(session, bin_dir);

            session.Log("Going to delete uninst.exe ...");
            cutil.del_file(session, uninstexe);

            var bindirparent = Path.GetDirectoryName(bin_dir);
            session.Log(@"Going to delete bindir\..\salt\*.*    ...   " + bindirparent);
            if (Directory.Exists(bindirparent)) {
                try { foreach (FileInfo fi in new DirectoryInfo(bindirparent).GetFiles("salt*.*")) { fi.Delete(); } } catch (Exception) {; }
            }
            session.Log("...END del_NSIS_DECAC");
            return ActionResult.Success;
        }


        //----------------------------------------------------------------------------
        //----------------------------------------------------------------------------
        //----------------------------------------------------------------------------



        static void Main(string[] args) {
            Console.WriteLine("DebugMe!");
            Session the_session = new Session();
            //del_NSIS_DECAC(the_session);

            String the_master= "";
            String the_id = "bob";
            string the_multimasters = "anna1,anna2";

            //read_master_and_id_from_file_IMCAC(the_session, @"c:\temp\testme.txt", ref the_master, ref the_id);

            write_master_and_id_to_file_DECAC(the_session, @"c:\temp\testme.txt", the_multimasters, the_id);

        }
    }
}

