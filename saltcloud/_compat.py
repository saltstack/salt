# -*- coding: utf-8 -*-
'''
Salt Cloud compatibility code
'''
try:
    # Python >2.5
    import xml.etree.cElementTree as ElementTree
except ImportError:
    try:
        # Python >2.5
        import xml.etree.ElementTree as ElementTree
    except ImportError:
        try:
            # normal cElementTree install
            import elementtree.cElementTree as ElementTree
        except ImportError:
            try:
                # normal ElementTree install
                import elementtree.ElementTree as ElementTree
            except ImportError:
                raise
