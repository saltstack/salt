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

<!-- BEGIN remove component for python.exe from dist-amd64.wxs because it must be in service.wxs -->
<!--
<xsl:key name="excludepython" match="wix:Component[contains(wix:File/@Source, 'python.exe')]" use="@Id"/>
<xsl:template match="wix:Component[key('excludepython', @Id)]"/>
<xsl:template match="wix:ComponentRef[key('excludepython', @Id)]"/>
-->
<!-- END remove component for python.exe from dist-amd64.wxs because it must be in service.wxs -->

<!-- BEGIN remove component for ssm.exe from dist-amd64.wxs because it must be in service.wxs -->
<!--key to detect ssmexe-->
<xsl:key name="ssmexe" match="wix:Component[contains(wix:File/@Source, '\ssm.exe')]" use="@Id"/>

<!--Match and ignore ssmexe  -->
<xsl:template match="wix:Component[key('ssmexe', @Id)]"/>
<xsl:template match="wix:ComponentRef[key('ssmexe', @Id)]"/>
<!-- END  remove component for ssm.exe from dist-amd64.wxs because it must be in service.wxs -->


<!--key to detect conf/minion file -->
<!--                                                          ends-with  ~  substring (A, string-length(A) - string-length(B) + 1)    -->
<xsl:key name="conf_minion_key" match="wix:Component['conf\minion' = substring(wix:File/@Source, string-length(wix:File/@Source) - 10)]" use="@Id"/>

<!--void Component Guid, so conf/minion is not removed on UNINSTALL -->
<xsl:template match="wix:Component[key('conf_minion_key', @Id)]">
  <xsl:copy>
    <xsl:attribute name="Guid">
      <xsl:value-of select="''"/>
    </xsl:attribute>
    <xsl:apply-templates select="@*[local-name()!='Guid']|node()"/>
  </xsl:copy>
</xsl:template>


</xsl:stylesheet>
