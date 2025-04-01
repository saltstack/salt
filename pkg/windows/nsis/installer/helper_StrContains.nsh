#------------------------------------------------------------------------------
# StrContains
#
# This function does a case sensitive searches for an occurrence of a substring in a string.
# It returns the substring if it is found.
# Otherwise it returns null("").
# Written by kenglish_hi
# Adapted from StrReplace written by dandaman32
#------------------------------------------------------------------------------
!define StrContains "!insertmacro StrContains"
!macro StrContains OUT NEEDLE HAYSTACK
    Push "${HAYSTACK}"
    Push "${NEEDLE}"
    Call StrContains
    Pop  "${OUT}"
!macroend
Function StrContains

    # Initialize variables
    Var /GLOBAL STR_HAYSTACK
    Var /GLOBAL STR_NEEDLE
    Var /GLOBAL STR_CONTAINS_VAR_1
    Var /GLOBAL STR_CONTAINS_VAR_2
    Var /GLOBAL STR_CONTAINS_VAR_3
    Var /GLOBAL STR_CONTAINS_VAR_4
    Var /GLOBAL STR_RETURN_VAR

    Exch $STR_NEEDLE
    Exch 1
    Exch $STR_HAYSTACK
    # Uncomment to debug
    #MessageBox MB_OK 'STR_NEEDLE = $STR_NEEDLE STR_HAYSTACK = $STR_HAYSTACK '
    StrCpy $STR_RETURN_VAR ""
    StrCpy $STR_CONTAINS_VAR_1 -1
    StrLen $STR_CONTAINS_VAR_2 $STR_NEEDLE
    StrLen $STR_CONTAINS_VAR_4 $STR_HAYSTACK

    loop:
        IntOp $STR_CONTAINS_VAR_1 $STR_CONTAINS_VAR_1 + 1
        StrCpy $STR_CONTAINS_VAR_3 $STR_HAYSTACK $STR_CONTAINS_VAR_2 $STR_CONTAINS_VAR_1
        StrCmp $STR_CONTAINS_VAR_3 $STR_NEEDLE found
        StrCmp $STR_CONTAINS_VAR_1 $STR_CONTAINS_VAR_4 done
        Goto loop

    found:
        StrCpy $STR_RETURN_VAR $STR_NEEDLE
        Goto done

    done:
        Pop $STR_NEEDLE  # Prevent "invalid opcode" errors and keep the stack clean
        Exch $STR_RETURN_VAR
FunctionEnd
