using System;
using Microsoft.Deployment.WindowsInstaller;
using System.IO;
using System.Text.RegularExpressions;
using Microsoft.Tools.WindowsInstallerXml;

namespace MinionConfigurationExtension
{
    public class MinionConfiguration : WixExtension
    {
        [CustomAction]
        public static ActionResult SetRootDir(Session session)
        {
            session.Message(InstallMessage.ActionStart, new Record("SetRootDir", "Configuring minion root_dir setting", "[1]"));
            session.Message(InstallMessage.Progress, new Record(0, 5, 0, 0));

            session.Log("Begin SetRootDir");
            string rootDir;

            try
            {
                rootDir = session[session["MINION_ROOT"]];
            }
            catch (Exception ex)
            {
                // missing MINION_ROOT
                session.Log("Exception: {0}", ex.Message.ToString());
                session.Log(ex.StackTrace.ToString());
                return ActionResult.Failure;
            }

            session.Message(InstallMessage.Progress, new Record(2, 1));

            bool result = processConfigChange(session,rootDir,"^root_dir:",String.Format("root_dir: {0}\n",rootDir));

            session.Message(InstallMessage.Progress, new Record(2, 1));

            session.Log("End SetRootDir");
            return result ? ActionResult.Success : ActionResult.Failure;
        }

        [CustomAction]
        public static ActionResult SetMaster(Session session)
        {
            session.Message(InstallMessage.ActionStart, new Record("SetMaster", "Configuring minion master setting", "[1]"));
            session.Message(InstallMessage.Progress, new Record(0, 5, 0, 0));
            
            session.Log("Begin SetMaster");

            string hostname;

            try
            {
                hostname = session["MASTER_HOSTNAME"];
            }
            catch (Exception ex)
            {
                // missing MASTER_HOSTNAME
                session.Log("Exception: {0}", ex.Message.ToString());
                session.Log(ex.StackTrace.ToString());
                return ActionResult.Failure;
            }

            session.Message(InstallMessage.Progress, new Record(2, 1));

            bool result = processConfigChange(session,session[session["MINION_ROOT"]],"^#*master:",String.Format("master: {0}\n",hostname));

            session.Message(InstallMessage.Progress, new Record(2, 1));

            session.Log("End SetMaster");
            return result ? ActionResult.Success : ActionResult.Failure;
        }

        [CustomAction]
        public static ActionResult SetMinionId(Session session)
        {
            session.Message(InstallMessage.ActionStart, new Record("SetMinionId", "Configuring minion id setting", "[1]"));
            session.Message(InstallMessage.Progress, new Record(0, 5, 0, 0));

            session.Log("Begin SetMinionId");

            string hostname;

            try
            {
                hostname = session["MINION_HOSTNAME"];
            }
            catch (Exception ex)
            {
                // missing MINION_HOSTNAME
                session.Log("Exception: {0}", ex.Message.ToString());
                session.Log(ex.StackTrace.ToString());
                return ActionResult.Failure;
            }

            session.Message(InstallMessage.Progress, new Record(2, 1));

            bool result = processConfigChange(session,session[session["MINION_ROOT"]],"^#*id:",String.Format("id: {0}\n",hostname));

            session.Message(InstallMessage.Progress, new Record(2, 1));

            session.Log("End SetMinionId");
            return result ? ActionResult.Success : ActionResult.Failure;
        }

        private static bool processConfigChange(Session session, string root, string pattern, string replacement)
        {
            string config;
            string[] configText;

            try
            {
                config = root + "conf\\minion";
            }
            catch (Exception ex)
            {
                session.Log("Exception: {0}", ex.Message.ToString());
                session.Log(ex.StackTrace.ToString());
                return false;
            }

            session.Message(InstallMessage.Progress, new Record(2, 1));
            session.Log("Config file: {0}", config);

            try
            {
                configText = File.ReadAllLines(config);
            }
            catch (Exception ex)
            {
                session.Log("Exception: {0}", ex.Message.ToString());
                session.Log(ex.StackTrace.ToString());
                return false;
            }

            session.Message(InstallMessage.Progress, new Record(2, 1));

            try
            {
                for (int i=0; i < configText.Length; i++)
                {
                    if (Regex.IsMatch(configText[i], pattern))
                    {
                        configText[i] = replacement;
                        session.Log("Set line: {0}", configText[i]);
                    }
                }
            }
            catch (Exception ex)
            {
                session.Log("Exception: {0}", ex.Message.ToString());
                session.Log(ex.StackTrace.ToString());
                return false;
            }

            session.Message(InstallMessage.Progress, new Record(2, 1));

            try
            {
                File.WriteAllLines(config, configText);
            }
            catch (Exception ex)
            {
                session.Log("Exception: {0}", ex.Message.ToString());
                session.Log(ex.StackTrace.ToString());
                return false;
            }

            return true;
        }
    }
}
