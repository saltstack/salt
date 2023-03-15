<?xml version="1.0" encoding="utf-8"?>
<!-- Adapted from http://www.lines-davies.net/blog/?p=12 -->
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
xmlns:wix="http://schemas.microsoft.com/wix/2006/wi"
xmlns:msxsl="urn:schemas-microsoft-com:xslt" exclude-result-prefixes="msxsl">

<xsl:output method="xml" indent="yes"/>

<!--Identity Transform -->
<xsl:template match="@*|node()">
  <xsl:copy>
    <xsl:apply-templates select="@*|node()"/>
  </xsl:copy>
</xsl:template>


<!--key to detect conf/minion file -->
<!--                                          ends-with  WORKAROUND  substring(A,                length(A)                      - length(B) + 1)    -->
<xsl:key name="conf_minion_key" match="wix:Component['conf\minion' = substring(wix:File/@Source, string-length(wix:File/@Source) - 10)]" use="@Id"/>

<!--Remove the Guid, so conf/minion is left behind on UNINSTALL -->
<xsl:template match="wix:Component[key('conf_minion_key', @Id)]">
  <xsl:copy>
    <xsl:attribute name="Guid">
      <xsl:value-of select="''"/>
    </xsl:attribute>
    <xsl:apply-templates select="@*[local-name()!='Guid']|node()"/>
  </xsl:copy>
</xsl:template>


<!-- This is the XSL madness copied for the case you harvest not ROOTDIR but CONFDIR -->
<!--key to detect minion file -->
<!--                                     ends-with  WORKAROUND  substring(A,                length(A)                      - length(B) + 1)    -->
<xsl:key name="conf_minion_key2" match="wix:Component['minion' = substring(wix:File/@Source, string-length(wix:File/@Source) - 5)]" use="@Id"/>

<!--Remove the Guid, so minion is left behind on UNINSTALL -->
<xsl:template match="wix:Component[key('conf_minion_key2', @Id)]">
  <xsl:copy>
    <xsl:attribute name="Guid">
      <xsl:value-of select="''"/>
    </xsl:attribute>
    <xsl:apply-templates select="@*[local-name()!='Guid']|node()"/>
  </xsl:copy>
</xsl:template>


</xsl:stylesheet>
