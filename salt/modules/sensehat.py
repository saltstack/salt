"""
Module for controlling the LED matrix or reading environment data on the SenseHat of a Raspberry Pi.

.. versionadded:: 2017.7.0

:maintainer:    Benedikt Werner <1benediktwerner@gmail.com>, Joachim Werner <joe@suse.com>
:maturity:      new
:depends:       sense_hat Python module

The rotation of the Pi can be specified in a pillar.
This is useful if the Pi is used upside down or sideways to correct the orientation of the image being shown.

Example:

.. code-block:: yaml

    sensehat:
        rotation: 90

"""


import logging

try:
    from sense_hat import SenseHat

    has_sense_hat = True
except (ImportError, NameError):
    _sensehat = None
    has_sense_hat = False

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load the module if SenseHat is available
    """
    if has_sense_hat:
        try:
            _sensehat = SenseHat()
        except OSError:
            return (
                False,
                "This module can only be used on a Raspberry Pi with a SenseHat.",
            )

        rotation = __salt__["pillar.get"]("sensehat:rotation", 0)
        if rotation in [0, 90, 180, 270]:
            _sensehat.set_rotation(rotation, False)
        else:
            log.error("%s is not a valid rotation. Using default rotation.", rotation)
        return True

    return (
        False,
        "The SenseHat execution module cannot be loaded: 'sense_hat' python library"
        " unavailable.",
    )


def set_pixels(pixels):
    """
    Sets the entire LED matrix based on a list of 64 pixel values

    pixels
        A list of 64 ``[R, G, B]`` color values.
    """
    _sensehat.set_pixels(pixels)
    return {"pixels": pixels}


def get_pixels():
    """
    Returns a list of 64 smaller lists of ``[R, G, B]`` pixels representing the
    the currently displayed image on the LED matrix.

    .. note::
        When using ``set_pixels`` the pixel values can sometimes change when
        you read them again using ``get_pixels``. This is because we specify each
        pixel element as 8 bit numbers (0 to 255) but when they're passed into the
        Linux frame buffer for the LED matrix the numbers are bit shifted down
        to fit into RGB 565. 5 bits for red, 6 bits for green and 5 bits for blue.
        The loss of binary precision when performing this conversion
        (3 bits lost for red, 2 for green and 3 for blue) accounts for the
        discrepancies you see.

        The ``get_pixels`` method provides an accurate representation of how the
        pixels end up in frame buffer memory after you have called ``set_pixels``.
    """
    return _sensehat.get_pixels()


def set_pixel(x, y, color):
    """
    Sets a single pixel on the LED matrix to a specified color.

    x
        The x coordinate of the pixel. Ranges from 0 on the left to 7 on the right.
    y
        The y coordinate of the pixel. Ranges from 0 at the top to 7 at the bottom.
    color
        The new color of the pixel as a list of ``[R, G, B]`` values.

    CLI Example:

    .. code-block:: bash

        salt 'raspberry' sensehat.set_pixel 0 0 '[255, 0, 0]'
    """
    _sensehat.set_pixel(x, y, color)
    return {"color": color}


def get_pixel(x, y):
    """
    Returns the color of a single pixel on the LED matrix.

    x
        The x coordinate of the pixel. Ranges from 0 on the left to 7 on the right.
    y
        The y coordinate of the pixel. Ranges from 0 at the top to 7 at the bottom.

    .. note::
        Please read the note for ``get_pixels``
    """
    return _sensehat.get_pixel(x, y)


def low_light(low_light=True):
    """
    Sets the LED matrix to low light mode. Useful in a dark environment.

    CLI Example:

    .. code-block:: bash

        salt 'raspberry' sensehat.low_light
        salt 'raspberry' sensehat.low_light False
    """
    _sensehat.low_light = low_light
    return {"low_light": low_light}


def show_message(
    message, msg_type=None, text_color=None, back_color=None, scroll_speed=0.1
):
    """
    Displays a message on the LED matrix.

    message
        The message to display
    msg_type
        The type of the message. Changes the appearance of the message.

        Available types are::

            error:      red text
            warning:    orange text
            success:    green text
            info:       blue text

    scroll_speed
        The speed at which the message moves over the LED matrix.
        This value represents the time paused for between shifting the text
        to the left by one column of pixels. Defaults to '0.1'.
    text_color
        The color in which the message is shown. Defaults to '[255, 255, 255]' (white).
    back_color
        The background color of the display. Defaults to '[0, 0, 0]' (black).

    CLI Example:

    .. code-block:: bash

        salt 'raspberry' sensehat.show_message 'Status ok'
        salt 'raspberry' sensehat.show_message 'Something went wrong' error
        salt 'raspberry' sensehat.show_message 'Red' text_color='[255, 0, 0]'
        salt 'raspberry' sensehat.show_message 'Hello world' None '[0, 0, 255]' '[255, 255, 0]' 0.2
    """
    text_color = text_color or [255, 255, 255]
    back_color = back_color or [0, 0, 0]

    color_by_type = {
        "error": [255, 0, 0],
        "warning": [255, 100, 0],
        "success": [0, 255, 0],
        "info": [0, 0, 255],
    }

    if msg_type in color_by_type:
        text_color = color_by_type[msg_type]

    _sensehat.show_message(message, scroll_speed, text_color, back_color)
    return {"message": message}


def show_letter(letter, text_color=None, back_color=None):
    """
    Displays a single letter on the LED matrix.

    letter
        The letter to display
    text_color
        The color in which the letter is shown. Defaults to '[255, 255, 255]' (white).
    back_color
        The background color of the display. Defaults to '[0, 0, 0]' (black).

    CLI Example:

    .. code-block:: bash

        salt 'raspberry' sensehat.show_letter O
        salt 'raspberry' sensehat.show_letter X '[255, 0, 0]'
        salt 'raspberry' sensehat.show_letter B '[0, 0, 255]' '[255, 255, 0]'
    """
    text_color = text_color or [255, 255, 255]
    back_color = back_color or [0, 0, 0]

    _sensehat.show_letter(letter, text_color, back_color)
    return {"letter": letter}


def show_image(image):
    """
    Displays an 8 x 8 image on the LED matrix.

    image
        The path to the image to display. The image must be 8 x 8 pixels in size.

    CLI Example:

    .. code-block:: bash

        salt 'raspberry' sensehat.show_image /tmp/my_image.png
    """
    return _sensehat.load_image(image)


def clear(color=None):
    """
    Sets the LED matrix to a single color or turns all LEDs off.

    CLI Example:

    .. code-block:: bash

        salt 'raspberry' sensehat.clear
        salt 'raspberry' sensehat.clear '[255, 0, 0]'
    """
    if color is None:
        _sensehat.clear()
    else:
        _sensehat.clear(color)
    return {"color": color}


def get_humidity():
    """
    Get the percentage of relative humidity from the humidity sensor.
    """
    return _sensehat.get_humidity()


def get_pressure():
    """
    Gets the current pressure in Millibars from the pressure sensor.
    """
    return _sensehat.get_pressure()


def get_temperature():
    """
    Gets the temperature in degrees Celsius from the humidity sensor.
    Equivalent to calling ``get_temperature_from_humidity``.

    If you get strange results try using ``get_temperature_from_pressure``.
    """
    return _sensehat.get_temperature()


def get_temperature_from_humidity():
    """
    Gets the temperature in degrees Celsius from the humidity sensor.
    """
    return _sensehat.get_temperature_from_humidity()


def get_temperature_from_pressure():
    """
    Gets the temperature in degrees Celsius from the pressure sensor.
    """
    return _sensehat.get_temperature_from_pressure()
