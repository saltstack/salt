*******************************
*******************************
*******************************
*******************************


		 * 2016-11.15  mkr
				If I set TargetFrameworkVersion to v4.0, in order to access the 32bit registry from 64bit Windows
				0) The code
						static RegistryKey wrGetKey(string k, bool sw32) {
								return RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, sw32 ? RegistryView.Registry32 : RegistryView.Registry64).OpenSubKey(k);
						}
				1) I get a warning that make no sense
				C:\windows\Microsoft.NET\Framework\v4.0.30319\Microsoft.Common.targets(983,5): warning MSB3644: The reference assemblies for framework ".
				NETFramework,Version=v4.0" were not found. To resolve this, install the SDK or Targeting Pack for this framework version or retarget your a
				pplication to a version of the framework for which you have the SDK or Targeting Pack installed. Note that assemblies will be resolved from
				the Global Assembly Cache (GAC) and will be used in place of reference assemblies. Therefore your assembly may not be correctly targeted f
				or the framework you intend. [C:\git\salt-windows-msi\wix\MinionConfigurationExtension\MinionConfigurationExtension.csproj]
					whereas the log contains
				SFXCA: Binding to CLR version v4.0.30319

				2) This program finds the 32 bit NSIS in the 64 bit registry.
					This is no good.

				I postpone to understand this and do not change TargetFrameworkVersion (leaving it at v2.0).



*******************************
*******************************
*******************************
*******************************


Archive for the attempt to read settings from conf/minion into a ini file.

Idea was
 1) read simple keys from the config file into a ini file
 2) read properties from ini file.

 Idea failed because reading ini files (in Appsearch) always preceeds reading a config file in Customaction before="Appsearch".

 The ini file  Search path is c:\windows

 The ini file is  read by WiX IniFileSearch in product.wxs


List<string> iniContent = new List<string>();
iniContent.Add("[Backup]");
What should be the "known location" to store settings after uninstall?
string iniFilePath32 = @"C:\windows\system32\config\systemprofile\Local\SaltStack\Salt\";
string iniFilePath64 = @"C:\windows\SysWOW64\config\systemprofile\Local\SaltStack\Salt\";
string iniFile = iniFilePath32 + @"MinionConfigBackup.ini";
System.IO.Directory.CreateDirectory(iniFilePath32);
write_this(iniFile, iniContent.ToArray());

        private static void write_this(string thefile, string[] thecontent) {
            using (var fs = new FileStream(thefile, FileMode.OpenOrCreate, FileAccess.ReadWrite)) {
                using (var fw = new StreamWriter(fs)) {
                    foreach (string line in thecontent) {
                        fw.Write(line);
                        fw.Write(System.Environment.NewLine);
                    };
                    fw.Flush(); // Added
                }
                fs.Flush();
            }
        }
