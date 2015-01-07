<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:wix="http://schemas.microsoft.com/wix/2006/wi"
  xmlns:msxsl="urn:schemas-microsoft-com:xslt" exclude-result-prefixes="msxsl">

  <xsl:output method="xml" indent="yes"/>

<!--Identity Transform-->
<xsl:template match="@*|node()">
  <xsl:copy>
    <xsl:apply-templates select="@*|node()"/>
  </xsl:copy>
</xsl:template>

<!--Set up keys for ignoring various file types-->
<xsl:key name="salt-minion-search" match="wix:Component[contains(wix:File/@Source, '$(var.dist)\salt-minion.exe')]" use="@Id"/>

<!--Match and ignore .config files-->
<xsl:template match="wix:Component[key('salt-minion-search', @Id)]"/>
<xsl:template match="wix:ComponentRef[key('salt-minion-search', @Id)]"/>

</xsl:stylesheet>
