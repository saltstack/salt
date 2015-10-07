/*custom webhelp*/
var windowheight = $( window ).height();

$( document ).ready(function() {

    /*adjust dev branch notification*/
    if ($( '#dev-notification' ).length ) {
        $( '#dev-notification', '.dev-notification-text' ).width($( '.navbar-header' ).width());
        $( '.navbar-header' ).css("padding-top", $( '#dev-notification' ).height() + 10);
    }

    /*insert links to module functions*/
    if ($( 'a.current' ).length && $( 'dt .headerlink' ).length ) {
        if (window.location.href.indexOf('/ref/cli/') == -1) {
            var tgt = $( 'a.current' );
            tgt.after('<ul id="function-list"></ul>');
            $('dt .headerlink').each(function(idx, elem) {
                var i = [
                '<li><a class="function-nav-link" href="', elem.href, '">',
                last(elem.href.split('.')),
                '</a></li>']
                .join('');
                $( '#function-list' ).append(i);
            });
        }
    }

    /*scroll the right-hand navigation*/
    var wheight = $( window ).height() - $( '#sidebar-static' ).height() - $( '#sidebar-static-bottom' ).height();
    $(function(){
        $( '#sidebar-nav' ).slimScroll({
            width: 'inherit',
            size: '14px',
            height: wheight
        }).promise().done(function() {

            if (window.location.hash) {
                var hash = window.location.hash.substring(1);
                var $link = $( '#sidebar-nav').find('a[href$="#' + hash + '"]').addClass("selected");
                if ($link.length) {
                    var scrollTo_val = $link.offset().top - ($( '#sidebar-static' ).height() + 40) + 'px';
                    $( '#sidebar-nav' ).slimScroll({ scrollTo : scrollTo_val });
                }
                else if ($( 'a.current' ).length) {
                    var scrollTo_val = $( 'a.current' ).offset().top - ($( '#sidebar-static' ).height() + 40) + 'px';
                    $( '#sidebar-nav' ).slimScroll({ scrollTo : scrollTo_val });
                }
            }
            else if ($( 'a.current' ).length) {
                var scrollTo_val = $( 'a.current' ).offset().top - ($( '#sidebar-static' ).height() + 40) + 'px';
                $( '#sidebar-nav' ).slimScroll({ scrollTo : scrollTo_val });
            }
            /*hidden by css - make visible after slimScroll plug-in loads*/
            $( '#sidebar-wrapper').css('visibility','visible');
        });
    });

    /*permalink display*/
    $( 'a.headerlink').html( '<span class="permalink"><i  data-container="body" data-toggle="tooltip" data-placement="bottom" title="Link to this location" class="glyphicon glyphicon-link"></i></span>');

    $( 'h1,h2,h3,h4,h5,h6').mouseenter(function(){
       $(this).find( '.permalink' ).find( 'i' ).css({'color':'#000'});
    }).mouseleave(function(){
        $(this).find( '.permalink' ).find( 'i' ).css({'color':'#fff'});
    });

    /*smooth on-page scrolling for long topic*/
    $( '#sidebar-nav' ).on('click','a[href^="#"]',function (e) {
        e.preventDefault();
        $( '#sidebar-nav' ).find( 'a' ).removeClass('selected');
        $(this).addClass('selected');
        var target = this.hash;
        var $target = $(target);

        $('html, body').stop().animate({
            'scrollTop': $target.offset().top
        }, 900, 'swing', function () {
            window.location.hash = target;
        });
    });

    /*scroll to active topic*/
    $( '#sidebar-nav' ).on('click','a.function-nav-link',function (e) {
        e.preventDefault();
        $( 'a.function-nav-link' ).removeClass('selected');
        $(this).addClass('selected');
        var target = this.hash.substring(1);
        var $target = $('dt[id="' + target + '"]');

        $('html, body').stop().animate({
            'scrollTop': $target.offset().top
        }, 900, 'swing', function () {
            window.location.hash = target;
        });
    });

    /*search form*/
    $( '#search-form' ).find( 'input' ).keypress(function(e) {
        if(e.which == 13) {
            var cx = '004624818632696854117:yfmprrbw3pk&q=';
            'find which search instance to use'
            if (DOCUMENTATION_OPTIONS.SEARCH_CX) {
                cx = DOCUMENTATION_OPTIONS.SEARCH_CX;
            }
            var searchterm = encodeURIComponent($(this).val());
            $(this).val("");
            window.location.href = 'https://www.google.com/cse?cx=' + cx + '&q=' + searchterm;
        }
    });

    /*menu collapse*/
    $( '#menu-toggle' ).click(function(e) {
        e.preventDefault();
        $( '#wrapper' ).toggleClass( 'toggled' );
    });

    /*version page selector*/
    $( 'div.releaselinks' ).on('click', 'a', function (e) {
        e.preventDefault();
        var clickedVer = $(this).attr("href");
        var $currentVer = $( 'div.versions' ).find( 'a.active' ).first();
        if (window.location.href.indexOf(clickedVer) == -1) {
            window.location.href = window.location.href.replace($currentVer.attr("href"), clickedVer);
        }
        else {
            if ($currentVer.text().indexOf("Develop") == -1) {
                window.location.href = clickedVer + "topics/releases/" + $currentVer.text().trim() + ".html";
            }
            else window.location.href = clickedVer + "topics/releases/";
        }
    });

    /*lightbox around images*/
    $( 'img' ).not( '.nolightbox' ).each(function() {
        var source = $(this).attr( 'src' );
        var id = $(this).attr( 'id' );
        $(this).wrap('<a href="'+ source + '" data-lightbox="' + id + '"></a>' )
    });

    /*enable bootstrap tooltips*/
    $(function () {
        $('[data-toggle="tooltip"]').tooltip();
    });

    /*notification box*/
    var box;
    $("#notifications").on('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        $.get('//docs.saltstack.com/en/announcements.html?id=1', function (data) {
            box = bootbox.dialog({
                title: "Announcements",
                message: data
            });
        _gaq.push(['_trackEvent', 'docs', 'announcement-view']);
        });
    });
    $(document).on('click', '.bootbox', function (event) {
        box.modal('hide');
    });
}); // $.document.ready

//refresh on window resize
var rtime = new Date(1, 1, 2000, 12,00,00);
var timeout = false;
var delta = 200;
$(window).resize(function() {

    if (!$( '#menu-toggle' ).is(":visible")) {
        rtime = new Date();
        if (timeout === false) {
            timeout = true;
            setTimeout(resizeend, delta);
        }
    }
});

function resizeend() {
    if (new Date() - rtime < delta) {
        setTimeout(resizeend, delta);
    } else {
        timeout = false;
        if ($( window ).height() > windowheight || $( window ).height() + 40 < windowheight) {
            location.reload(false);
        }
    }
}

function last(list) {
    return list[list.length - 1];
}
