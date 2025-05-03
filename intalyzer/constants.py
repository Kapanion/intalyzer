ARDUINO_WRAPPER = """
#include <Arduino.h>
#include <avr/io.h>
#include <avr/interrupt.h>

void setup();
void loop();

"""

ARDUINO_WRAPPER_LINES = ARDUINO_WRAPPER.count("\n")
