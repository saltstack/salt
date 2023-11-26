2016-11-16  mkr
This regards ISSUE 1  
     https://github.com/markuskramerIgitt/salt-windows-msi/issues/1
     uninstall removes the configuration file


Heat collects files into XML file salt-windows-msi\wix\MinionMSI\dist-amd64.wxs

The entry for conf/minion has a Guid:

            <Component Id="cmpF3CE08C037F32A1C76DF93B02A6ACB79" Directory="dirA7CC33A34163812EEAF3B20CD074A564" Guid="{357ECA3A-24C0-49C5-9964-6CF9504168C4}">
                <File Id="filF7B75C18646D054B4C42FBFF0826EBA7" KeyPath="yes" Source="$(var.dist)\conf\minion" />
            </Component>

Having a Guid means that Wix treats conf/minion as part of the installation
On uninstall, WiX removed all parts of the installation, so also conf/minion.

This is unwanted behaviour.

Approach 1: FAIL
  exclude the component
  BuildDistFragment.xsl does  that.
  It filters out ssm.exe, so ssm.exe is not in salt-windows-msi\wix\MinionMSI\dist-amd64.wxs
  ssm.exe is added manually in services.wxs.
  FAILURE (I think) because then conf would not be installed.  


Approach 2:
  Remove the GUID of the component.

http://stackoverflow.com/questions/11848780/use-ends-with-in-xslt-v1-0

set attribute to a value while copying:
   http://stackoverflow.com/questions/1137078/xslt-do-not-match-certain-attributes/12919373#12919373
