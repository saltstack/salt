using Microsoft.Tools.WindowsInstallerXml;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;

// General Information about an assembly is controlled through the following
// set of attributes. Change these attribute values to modify the information
// associated with an assembly.
[assembly: AssemblyTitle("MinionConfigurationExtension")]
[assembly: AssemblyDescription("Custom Actions for the Salt Minion MSI")]
[assembly: AssemblyCompany("SaltStack, Inc")]
[assembly: AssemblyProduct("MinionConfigurationExtension")]
[assembly: AssemblyCopyright("Copyright © SaltStack, Inc 2014")]
[assembly: AssemblyTrademark("")]
[assembly: AssemblyCulture("")]

[assembly: AssemblyDefaultWixExtension(typeof(MinionConfigurationExtension.MinionConfiguration))]

// Setting ComVisible to false makes the types in this assembly not visible
// to COM components.  If you need to access a type in this assembly from
// COM, set the ComVisible attribute to true on that type.
[assembly: ComVisible(false)]

// The following GUID is for the ID of the typelib if this project is exposed to COM
[assembly: Guid("ead7bf40-ca47-41e2-8187-6c346cccb46a")]

// Version information for an assembly consists of the following four values:
//
//      Major Version
//      Minor Version
//      Build Number
//      Revision
//
// You can specify all the values or you can default the Build and Revision Numbers
// by using the '*' as shown below:
// [assembly: AssemblyVersion("1.0.*")]
[assembly: AssemblyVersion("1.0.0.0")]
[assembly: AssemblyFileVersion("1.0.0.0")]
