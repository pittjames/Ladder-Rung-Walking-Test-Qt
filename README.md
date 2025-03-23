# Ladder-Rung-Walking-Test-Qt
## Automated System for Mouse Ladder Rung Walking Test

This repository contains the software components for an automated ladder rung walking test system, designed to evaluate motor coordination in rodent models of neurological disorders. The system integrates a customized ladder apparatus with photoelectric sensors, an Arduino microcontroller, and a Python-Qt-based user interface for real-time data acquisition and visualization.

## Features
1. Automated detection of foot fault events using thru-beam and reflective photoelectric sensors
2. Real-time data visualization and analysis in a user-friendly Python-Qt interface
3. Configurable sensor parameters and trial settings
4. Data export and storage for offline analysis

## Hardware Requirements
1. Arduino Uno or compatible microcontroller board
2. Custom ladder rung apparatus with photoelectric sensors
3. USB cable for Arduino-PC communication

## Software Dependencies
1. Python 3.x
2. PyQt5
3. pyqtgraph
4. pyserial
5. Arduino IDE

## Usage

1. Connect the Arduino board to your computer via USB.
2. Run the Python Qt application: python sensor_visualization_app.py
3. In the application, select the correct serial port and baud rate (default 9600) for your Arduino connection. Click "Connect".
Configure the sensor pin assignments and debounce settings if needed. The default configuration is:
3.1 Foot Error Sensor on Arduino pin 2, debounce 200ms
3.2 Interface Sensor on Arduino pin 3, debounce 1000ms


5. Click "Start Trial" to begin a new trial. The app will start recording sensor events and display them on the chart in real-time.
6. Click "End Trial" to stop the current trial. The trial data will be saved internally.
7. Repeat steps 5-6 for additional trials as needed.
8. To save all trial data, click "Save Data" and choose a location to save the CSV file.

## Arduino Sketch
The ladder_rung_test.ino sketch is located in the arduino directory. It handles reading the sensor states, debouncing, and sending event data to the PC via serial communication.
