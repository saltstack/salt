using Microsoft.Deployment.WindowsInstaller;
using Microsoft.Tools.WindowsInstallerXml;
using Microsoft.Win32;
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Management;  // Reference C:\Windows\Microsoft.NET\Framework\v2.0.50727\System.Management.dll
using System.ServiceProcess;
using System.Text.RegularExpressions;


namespace MinionConfigurationExtension {
    public class cutil : WixExtension {
        //
        // DECAC means you must access data helper properties at session.CustomActionData[*]
        // IMCAC means ou can directly access msi properties at session[*]

        public static void del_file(Session session, string file) {
            try {
                File.Delete(file);
            } catch (Exception ex) {
                just_ExceptionLog("", session, ex);
            }
        }

        public static void del_dir(Session session, string a_dir, string sub_dir = "") {
            string abs_path = a_dir;
            if (sub_dir.Length > 0) {
                abs_path = Path.Combine(a_dir, sub_dir);
            }
            if (a_dir.Length>0 && Directory.Exists(a_dir) && Directory.Exists(abs_path)) {
                try {
                    session.Log("...del_dir " + abs_path);
                    Directory.Delete(abs_path, true);
                } catch (Exception ex) {
                    cutil.just_ExceptionLog("", session, ex);
                }
            }
        }

        /// <summary>
        /// Remove runtime Python bytecode under a managed install root: all
        /// __pycache__ directories (deepest first), then stray .pyc files, then prune
        /// directories that became empty. Safe if the tree is missing or partial.
        /// Used from MSI clear_python_caches_IMCAC and from DeleteConfig_DECAC (uninstall
        /// and DeleteConfig2 / CLEAN_INSTALL).
        /// </summary>
        public static void clear_python_bytecode_caches_under_dir(Session session, string installRoot) {
            if (installRoot == null) installRoot = "";
            installRoot = installRoot.Trim().TrimEnd('\\', '/');
            if (installRoot.Length == 0) {
                session.Log("...clear_python_bytecode_caches_under_dir: skip (empty path)");
                return;
            }
            if (!Directory.Exists(installRoot)) {
                session.Log("...clear_python_bytecode_caches_under_dir: skip (not found): " + installRoot);
                return;
            }
            session.Log("...clear_python_bytecode_caches_under_dir: " + installRoot);
            List<string> pycaches = new List<string>();
            try {
                Stack<string> stack = new Stack<string>();
                stack.Push(installRoot);
                while (stack.Count > 0) {
                    string dir = stack.Pop();
                    string[] subdirs;
                    try {
                        subdirs = Directory.GetDirectories(dir);
                    } catch (Exception ex) {
                        cutil.just_ExceptionLog("clear_pyc GetDirectories", session, ex);
                        continue;
                    }
                    foreach (string sub in subdirs) {
                        string leaf = Path.GetFileName(sub);
                        if (string.Compare(leaf, "__pycache__", StringComparison.OrdinalIgnoreCase) == 0)
                            pycaches.Add(sub);
                        else
                            stack.Push(sub);
                    }
                }
            } catch (Exception ex) {
                cutil.just_ExceptionLog("clear_pyc walk __pycache__", session, ex);
            }
            pycaches.Sort(delegate(string a, string b) { return b.Length.CompareTo(a.Length); });
            foreach (string p in pycaches) {
                try {
                    session.Log("...clear_python_bytecode_caches_under_dir: rmdir " + p);
                    Directory.Delete(p, true);
                } catch (Exception ex) {
                    cutil.just_ExceptionLog("clear_pyc rmdir", session, ex);
                }
            }
            try {
                Stack<string> stack = new Stack<string>();
                stack.Push(installRoot);
                while (stack.Count > 0) {
                    string dir = stack.Pop();
                    string[] files;
                    try {
                        files = Directory.GetFiles(dir, "*.pyc");
                    } catch (Exception ex) {
                        cutil.just_ExceptionLog("clear_pyc GetFiles", session, ex);
                        files = new string[0];
                    }
                    foreach (string f in files) {
                        try {
                            File.Delete(f);
                            session.Log("...clear_python_bytecode_caches_under_dir: del " + f);
                        } catch (Exception ex) {
                            cutil.just_ExceptionLog("clear_pyc del pyc", session, ex);
                        }
                    }
                    try {
                        foreach (string sub in Directory.GetDirectories(dir))
                            stack.Push(sub);
                    } catch (Exception ex) {
                        cutil.just_ExceptionLog("clear_pyc subdirs", session, ex);
                    }
                }
            } catch (Exception ex) {
                cutil.just_ExceptionLog("clear_pyc stray .pyc", session, ex);
            }
            remove_empty_directories_under(session, installRoot);
        }

        /// <summary>
        /// Delete leaf empty directories under installRoot (deepest first).
        /// Does not remove installRoot itself.
        /// </summary>
        private static void remove_empty_directories_under(Session session, string installRoot) {
            if (installRoot == null || installRoot.Length == 0 || !Directory.Exists(installRoot))
                return;
            string root;
            try {
                root = Path.GetFullPath(installRoot);
            } catch (Exception ex) {
                cutil.just_ExceptionLog("clear_pyc emptydirs root", session, ex);
                return;
            }
            List<string> dirs = new List<string>();
            try {
                foreach (string d in Directory.GetDirectories(root, "*", SearchOption.AllDirectories))
                    dirs.Add(d);
            } catch (Exception ex) {
                cutil.just_ExceptionLog("clear_pyc emptydirs enumerate", session, ex);
                return;
            }
            dirs.Sort(delegate(string a, string b) { return b.Length.CompareTo(a.Length); });
            foreach (string d in dirs) {
                if (!Directory.Exists(d))
                    continue;
                try {
                    if (string.Compare(Path.GetFullPath(d), root, StringComparison.OrdinalIgnoreCase) == 0)
                        continue;
                } catch (Exception ex) {
                    cutil.just_ExceptionLog("clear_pyc emptydirs norm", session, ex);
                    continue;
                }
                try {
                    if (Directory.GetFileSystemEntries(d).Length > 0)
                        continue;
                    session.Log("...clear_python_bytecode_caches_under_dir: rmdir empty " + d);
                    Directory.Delete(d, false);
                } catch (Exception ex) {
                    cutil.just_ExceptionLog("clear_pyc rmdir empty", session, ex);
                }
            }
        }


        public static void del_registry_key(Session session, String HKLM_reg_path) {
            try {
                session.Log("Going to delete HKLM registry key " +  HKLM_reg_path);
                RegistryKey HKLM = Registry.LocalMachine;
                if (HKLM.OpenSubKey(HKLM_reg_path) == null) {
                    session.Log("does not exist");
                }else{
                    session.Log("does exist. Now deleting");
                    HKLM.DeleteSubKeyTree(HKLM_reg_path);
                }
            } catch (Exception ex) {
                cutil.just_ExceptionLog("", session, ex);
            }
        }
        public static void del_registry_SOFTWARE_key(Session session, String SOFTWARE_reg_path) {
            try {
                session.Log("Going to delete SOFTWARE registry key " +  SOFTWARE_reg_path);
                del_registry_key(session, "SOFTWARE\\" + SOFTWARE_reg_path);
                del_registry_key(session, "SOFTWARE\\WoW6432Node\\" + SOFTWARE_reg_path);
            } catch (Exception ex) {
                cutil.just_ExceptionLog("", session, ex);
                }
        }

        public static RegistryKey get_registry_SOFTWARE_key(Session session, String SOFTWARE_reg_path) {
            try {
                session.Log("Going to get SOFTWARE registry key " +  SOFTWARE_reg_path);
                RegistryKey HKLM = Registry.LocalMachine;
                RegistryKey r64 =  HKLM.OpenSubKey("SOFTWARE\\" + SOFTWARE_reg_path);
                if (r64 != null) return r64;
                return HKLM.OpenSubKey("SOFTWARE\\WoW6432Node\\" + SOFTWARE_reg_path);
            } catch (Exception ex) {
                cutil.just_ExceptionLog("", session, ex);
            }
            return null;
        }


        public static void Write_file(Session session, string path, string filename, string filecontent) {
            System.IO.Directory.CreateDirectory(path);  // Creates all directories and subdirectories in the specified path unless they already exist
            File.WriteAllText(Path.Combine(path, filename), filecontent);       //  throws an Exception if path does not exist
            session.Log(@"...Write_file " + Path.Combine(path, filename));
        }


        public static void Writeln_file(Session session, string path, string filename, string filecontent) {
            Write_file(session, path, filename, filecontent + Environment.NewLine);
        }


        public static void Move_file(Session session, string ffn, string timestamp_bak) {
            string target = ffn + timestamp_bak;
            session.Log("...Move_file?   " + ffn);

            if (File.Exists(ffn)) {
                session.Log("...Move_file!   " + ffn);
                if (File.Exists(target)) {
                    session.Log("...target exists   " + target);
                } else {
                    File.Move(ffn, target);
                }
            }
        }


        public static void Move_dir(Session session, string ffn, string timestamp_bak, bool delete_target = false) {
            string target = ffn + timestamp_bak;
            session.Log("...Move_dir?   " + ffn);

            if (Directory.Exists(ffn)) {
                session.Log("...Move_dir!   " + ffn);
                if (Directory.Exists(target)) {
                    session.Log("...target exists   " + target);
                    if (delete_target) {
                        session.Log("...deleting target");
                        Directory.Delete(target, true);
                        Directory.Move(ffn, target);
                    }
                } else {
                    Directory.Move(ffn, target);
                }
            }
        }


        public static void movedir_fromAbs_toRel(Session session, string abs_from0, string rel_tmp_dir, bool into_safety, string safedir) {
            string abs_from;
            string abs_to;
            if (into_safety) {
                abs_from = abs_from0;
                abs_to = safedir + rel_tmp_dir;
            } else {
                abs_from = safedir + rel_tmp_dir;
                abs_to = abs_from0;
            }

            session.Log("...We may need to move? does directory exist " + abs_from);
            if (Directory.Exists(abs_from)) {
                session.Log(".....yes");
            } else {
                session.Log(".....no");
                return;
            }
            if (Directory.Exists(abs_to)) {
                session.Log("....!I must first delete the TO directory " + abs_to);
                shellout(session, @"rmdir /s /q " + abs_to);
            }
            // Now move
            try {
                session.Log("...now move to " + abs_to);

                Directory.Move(abs_from, abs_to);
                session.Log(".........ok");
            } catch (Exception ex) {
                just_ExceptionLog(@"...moving failed", session, ex);
            }
        }



        public static string get_property_IMCAC(Session session, string key ) {
            // IMMEDIATE means
            //   you can directly access msi properties at session[KEY]
            // keys are case sensitive
            // If key does not exist, its value will be empty
            session.Log("...get_property_IMCAC key {0}", key);
            string val = session[key];
            session.Log("...get_property_IMCAC val {0}", val);
            session.Log("...get_property_IMCAC len {0}", val.Length);
            return val;
        }


        public static string get_property_DECAC(Session session, string key) {
            // DEFERRED means
            //   you may modify the system because the transaction has started
            //   you must access msi properties via CustomActionData[KEY]
            // If key does not exist, the msi will fail to install
            session.Log("...get_property_DECAC key {0}", key);
            string val = session.CustomActionData[key];
            session.Log("...get_property_DECAC val {0}", val);
            session.Log("...get_property_DECAC len {0}", val.Length);
            return val;
        }



        public static void just_ExceptionLog(string description, Session session, Exception ex) {
            session.Log(" ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ");
            session.Log(description);
            session.Log("Exception: {0}", ex.Message.ToString());
            session.Log(ex.StackTrace.ToString());
        }

        public static string get_file_that_exist(Session session, string[] files) {
            foreach (var file in files) {
                session.Log("...looking for " + file);
                if (File.Exists(file)) {
                    session.Log("...found " + file);
                    return file;
                }
            }
            return "";
        }

        public static void shellout(Session session, string s) {
            // This is a handmade shellout routine
            session.Log("...shellout(" + s + ")");
            try {
                System.Diagnostics.Process process = new System.Diagnostics.Process();
                System.Diagnostics.ProcessStartInfo startInfo = new System.Diagnostics.ProcessStartInfo();
                startInfo.WindowStyle = System.Diagnostics.ProcessWindowStyle.Hidden;
                startInfo.FileName = "cmd.exe";
                startInfo.Arguments = "/C " + s;
                process.StartInfo = startInfo;
                process.Start();
                process.WaitForExit();
            } catch (Exception ex) {
                just_ExceptionLog("shellout tried " + s, session, ex);
            }
        }

    }
}
