import sys
import time
import serial
import json
import csv
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, 
                            QVBoxLayout, QHBoxLayout, QWidget, QLabel, 
                            QComboBox, QFileDialog, QGroupBox, QGridLayout,
                            QMessageBox, QStatusBar)
from PyQt5.QtCore import QTimer, Qt, pyqtSignal, QThread
from PyQt5.QtGui import QFont, QColor
import pyqtgraph as pg
import numpy as np

class SerialThread(QThread):
    """Thread for reading serial data in background"""
    data_received = pyqtSignal(str)
    config_received = pyqtSignal(dict)
    
    def __init__(self, port, baud_rate):
        super().__init__()
        self.port = port
        self.baud_rate = baud_rate
        self.running = False
        self.serial_port = None
        
    def run(self):
        try:
            print(f"Starting connection to Arduino: {self.port} at {self.baud_rate} baud")
            self.serial_port = serial.Serial(self.port, self.baud_rate, timeout=1)
            self.running = True
            print(f"Successfully connected to Arduino: {self.port}")
            
            while self.running:
                if self.serial_port.in_waiting > 0:
                    line = self.serial_port.readline().decode('utf-8').strip()
                    if line:
                        try:
                            # Check if this is a configuration message
                            data = json.loads(line)
                            if "config" in data:
                                self.config_received.emit(data)
                            else:
                                self.data_received.emit(line)
                        except json.JSONDecodeError:
                            # Not valid JSON, just pass it along
                            self.data_received.emit(line)
                time.sleep(0.01)
                
        except Exception as e:
            print(f"Serial error: {e}")
            self.running = False
        finally:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
    
    def stop(self):
        self.running = False
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self.wait()
    
    def send_command(self, command):
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.write((command + '\n').encode('utf-8'))
                return True
            except Exception as e:
                print(f"Error sending command: {e}")
                return False
        return False

class VerticalLineItem(pg.GraphicsObject):
    """Custom vertical line item for event visualization"""
    def __init__(self, x, y, height=0.7, width=1.5, color=None):
        pg.GraphicsObject.__init__(self)
        self.x = x
        self.y = y
        self.height = height  # Line height
        self.width = width    # Line width
        self.color = color if color else pg.mkPen('b', width=width)
        self.generatePicture()
        
    def generatePicture(self):
        """Generate the line picture"""
        self.picture = pg.QtGui.QPicture()
        p = pg.QtGui.QPainter(self.picture)
        p.setPen(self.color)
        # Draw vertical line centered at y with specified height
        p.drawLine(
            pg.QtCore.QPointF(self.x, self.y - self.height/2),
            pg.QtCore.QPointF(self.x, self.y + self.height/2)
        )
        p.end()
        
    def paint(self, p, *args):
        """Paint the line"""
        p.drawPicture(0, 0, self.picture)
        
    def boundingRect(self):
        """Return the bounding rectangle"""
        return pg.QtCore.QRectF(self.picture.boundingRect())

class SensorVisualizationApp(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Application settings
        self.setWindowTitle("Ladder Rungs Test Visualization Tool")
        self.setGeometry(100, 100, 900, 850)  # Adjusted window size
        
        # Data storage
        self.current_trial_data = []  # Current trial data
        self.all_trials_data = []     # All trials data
        self.trial_count = 0          # Trial counter
        self.start_time = None        # Record trial start time
        self.end_time = None          # Record trial end time
        self.is_recording = False     # Recording status
        
        # Number of sensors (now only 2)
        self.NUM_SENSORS = 2
        
        # Sensor trigger counts (now only 2 sensors)
        self.sensor_counts = [0, 0]  # Counts for two sensors
        
        # Debounce settings - individual times for each sensor (milliseconds)
        self.debounce_times = [200, 1000]  # Default 500ms for all sensors
        self.last_trigger_time = [0, 0]  # Last trigger time for each sensor
        
        # Default Arduino pin numbers for sensors
        self.arduino_pins = [2, 3]  # Default pin 2 for Foot Error Sensor, pin 3 for Interface Sensor
        
        # Sensor mapping from Arduino pin index to sensor index
        self.sensor_mapping = {
            0: 0,  # Arduino pin 2 (index 0) maps to sensor index 0 (Foot Error Sensor)
            1: 1   # Arduino pin 3 (index 1) maps to sensor index 1 (Interface Sensor)
        }
        
        # Create serial thread
        self.serial_thread = None
        
        # End trial line reference
        self.end_trial_line = None
        
        # Vertical line event items
        self.line_items = [[], []]  # Array of line items for each sensor
        
        # Arduino connection status
        self.arduino_connected = False
        
        # UI styling
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QGroupBox {
                border: 1px solid #ccc;
                border-radius: 5px;
                margin-top: 1em;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
            QPushButton {
                background-color: #4CAF50;
                border: none;
                color: white;
                padding: 8px 16px;
                text-align: center;
                text-decoration: none;
                font-size: 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
            QLabel {
                font-size: 14px;
            }
            QComboBox {
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 3px;
                min-height: 25px;
            }
        """)
        
        # Setup UI
        self.setup_ui()
        
        # Setup timer for updating chart (every 100ms)
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_plot)
        self.update_timer.start(100)
        
    def setup_ui(self):
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Control panel
        control_panel = QGridLayout()
        control_panel.setVerticalSpacing(15)
        control_panel.setHorizontalSpacing(15)
        
        # Serial settings group
        serial_group = QGroupBox("Serial Settings")
        serial_layout = QGridLayout() 
        
        self.port_label = QLabel("Port:")
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(150)  
        self.refresh_ports()  # Populate port options
        
        self.baud_label = QLabel("Baud Rate:")
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["9600", "19200", "38400", "57600", "115200"])  # Baud rate option
        self.baud_combo.setCurrentText("9600")  # default Baud rate to 9600
        
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.connect_disconnect)
        
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_ports)
        
        
        serial_layout.addWidget(self.port_label, 0, 0)
        serial_layout.addWidget(self.port_combo, 0, 1)
        serial_layout.addWidget(self.baud_label, 1, 0)
        serial_layout.addWidget(self.baud_combo, 1, 1)
        serial_layout.addWidget(self.connect_button, 0, 2)
        serial_layout.addWidget(self.refresh_button, 1, 2)
        serial_group.setLayout(serial_layout)
        
        # Arduino Pin Configuration Group
        pin_group = QGroupBox("Arduino Pin Configuration")
        pin_layout = QGridLayout()
        
        # Define sensor names and their default pins
        sensor_names = ["Foot Error Sensor", "Interface Sensor"]
        sensor_default_pins = [2, 3]
        
        # Create pin settings for each sensor
        self.pin_combos = []
        pin_options = [str(i) for i in range(2, 14)]  # Arduino Nano digital pins 2-13
        
        for i, name in enumerate(sensor_names):
            label = QLabel(f"{name} Pin:")
            combo = QComboBox()
            combo.addItems(pin_options)
            combo.setCurrentText(str(sensor_default_pins[i]))
            from functools import partial
            combo.currentTextChanged.connect(partial(self.update_sensor_pin, sensor_id=i))
            
            pin_layout.addWidget(label, i, 0)
            pin_layout.addWidget(combo, i, 1)
            self.pin_combos.append(combo)
        
        pin_group.setLayout(pin_layout)
        
        # Debounce settings group
        debounce_group = QGroupBox("Debounce Settings (ms)")
        debounce_layout = QGridLayout()
        
        # Create debounce settings for each sensor
        self.debounce_combos = []
        debounce_options = ["200", "500", "1000", "1500"]
        
        for i, name in enumerate(sensor_names):
            label = QLabel(f"{name}:")
            combo = QComboBox()
            combo.addItems(debounce_options)
            if i == 0:  # Foot Error Sensor
                combo.setCurrentText("200")  # Default to 200ms
            else:  # Interface Sensor
                combo.setCurrentText("1000")  # Default to 1000ms
            combo.currentTextChanged.connect(partial(self.update_sensor_debounce, sensor_id=i))
            
            debounce_layout.addWidget(label, i, 0)
            debounce_layout.addWidget(combo, i, 1)
            self.debounce_combos.append(combo)
        
        debounce_group.setLayout(debounce_layout)
        
        # Trial control group
        trial_group = QGroupBox("Trial Control")
        trial_layout = QHBoxLayout()
        
        self.start_button = QPushButton("Start Trial")
        self.start_button.clicked.connect(self.start_trial)
        self.start_button.setEnabled(False)
        
        self.stop_button = QPushButton("End Trial")
        self.stop_button.clicked.connect(self.stop_trial)
        self.stop_button.setEnabled(False)
        
        self.save_button = QPushButton("Save Data")
        self.save_button.clicked.connect(self.save_data)
        
        trial_layout.addWidget(self.start_button)
        trial_layout.addWidget(self.stop_button)
        trial_layout.addWidget(self.save_button)
        trial_group.setLayout(trial_layout)
        
        # Add control groups to control panel
        control_panel.addWidget(serial_group, 0, 0, 1, 2)
        control_panel.addWidget(pin_group, 1, 0)
        control_panel.addWidget(debounce_group, 1, 1)
        control_panel.addWidget(trial_group, 2, 0, 1, 2)
        
        main_layout.addLayout(control_panel)
        
        # Status indicators
        status_layout = QVBoxLayout()
        
        self.status_label = QLabel("Status: Not Connected")
        self.status_label.setStyleSheet("font-size: 14px; color: #666;")
        
        self.trial_label = QLabel("Current Trial: None")
        self.trial_label.setStyleSheet("font-size: 14px; color: #666;")
        
        # Add trial timer display
        self.timer_label = QLabel("Trial Time: 0.00s")
        self.timer_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #0066cc;")
        
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.trial_label)
        status_layout.addWidget(self.timer_label)
        main_layout.addLayout(status_layout)
        
        # Sensor count display
        counts_layout = QHBoxLayout()
        self.count_labels = []
        self.sensor_group_boxes = []  # Store direct references to the group boxes
        
        # Define specific sensor names for ladder rungs walking test (only 2 now)
        sensor_names = ["Foot Error Sensor", "Interface Sensor"]
        
        for i in range(self.NUM_SENSORS):
            # Include pin number in the title
            sensor_group = QGroupBox(f"{sensor_names[i]} (Pin {self.arduino_pins[i]})")
            self.sensor_group_boxes.append(sensor_group)  # Store reference
            
            sensor_layout = QVBoxLayout()
            count_label = QLabel("Trigger Count: 0")
            count_label.setStyleSheet("font-size: 16px; font-weight: bold;")
            self.count_labels.append(count_label)
            sensor_layout.addWidget(count_label)
            sensor_group.setLayout(sensor_layout)
            counts_layout.addWidget(sensor_group)
        
        main_layout.addLayout(counts_layout)
        
        # Chart
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('#ffffff')
        self.plot_widget.setLabel('left', 'Sensor')
        self.plot_widget.setLabel('bottom', 'Time (seconds)')
        self.plot_widget.setYRange(-0.5, 1.5)  # Only 2 sensors now
        
        # Set initial y-axis ticks - will be updated when pins change
        self.update_plot_axis_labels()
        
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.getAxis('left').setPen(pg.mkPen(color='k', width=1))
        self.plot_widget.getAxis('bottom').setPen(pg.mkPen(color='k', width=1))
        self.plot_widget.getAxis('left').setTextPen(pg.mkPen(color='k', width=1))
        self.plot_widget.getAxis('bottom').setTextPen(pg.mkPen(color='k', width=1))
        
        # Store event lines for each sensor
        self.event_lines = [[], []]
        main_layout.addWidget(self.plot_widget, stretch=1)
        
        # Set main widget
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        
        # Timer for updating the trial time display
        self.trial_timer = QTimer()
        self.trial_timer.timeout.connect(self.update_trial_time)
        self.trial_timer.setInterval(100)  # Update every 100ms
        
        # Add debug area in status bar
        self.statusBar = self.statusBar()
        self.debug_label = QLabel("No data")
        self.statusBar.addPermanentWidget(self.debug_label, 1)
        self.statusBar.setStyleSheet("QStatusBar { border-top: 1px solid #ccc; }")
    
    def update_plot_axis_labels(self):
        """Update just the plot Y-axis labels with current pin numbers"""
        self.plot_widget.getAxis('left').setTicks([
            [(0, f'Foot Error Sensor \n (Pin {self.arduino_pins[0]})'), 
             (1, f'Interface Sensor  \n (Pin {self.arduino_pins[1]})')]
        ])
    
    def update_pin_display(self):
        """Update all pin displays in the UI"""
        # Update sensor names in the count groups to include pin numbers
        sensor_names = ["Foot Error Sensor", "Interface Sensor"]
        
        # Use direct references to the group boxes
        for i in range(self.NUM_SENSORS):
            pin_number = self.arduino_pins[i]
            updated_name = f"{sensor_names[i]} (Pin {pin_number})"
            
            # Update the group box title using our direct reference
            if i < len(self.sensor_group_boxes):
                self.sensor_group_boxes[i].setTitle(updated_name)
                print(f"Updated sensor group box title: {updated_name}")
            else:
                print(f"Warning: sensor_group_boxes index {i} out of range")
        
        # Update the Y-axis labels in the plot
        self.update_plot_axis_labels()
        
        # Print debug information for verification
        print(f"UI updated - Pins: Foot Error Sensor (Pin {self.arduino_pins[0]}), Interface Sensor (Pin {self.arduino_pins[1]})")
    
    def update_trial_time(self):
        """Update the trial time display"""
        if self.is_recording and self.start_time:
            # Calculate elapsed time
            elapsed_time = time.time() - self.start_time
            # Update the label
            self.timer_label.setText(f"Trial Time: {elapsed_time:.2f}s")
    
    def update_sensor_pin(self, value, sensor_id):
        """Update the Arduino pin mapping for a specific sensor"""
        if not self.arduino_connected:
            QMessageBox.warning(self, "Not Connected", 
                               "Connect to Arduino first before changing pin configuration.")
            # Reset to previous value
            self.pin_combos[sensor_id].setCurrentText(str(self.arduino_pins[sensor_id]))
            return
            
        pin_number = int(value)
        # Update the Arduino pin number for this sensor
        self.arduino_pins[sensor_id] = pin_number
        
        # Update the sensor mapping
        # We need to recalculate the mapping from Arduino pin index to sensor index
        self.sensor_mapping = {}
        for i, pin in enumerate(self.arduino_pins):
            # Calculate Arduino pin index (0 for pin 2, 1 for pin 3, etc.)
            pin_index = pin - 2
            # Map this pin index to the sensor id
            self.sensor_mapping[pin_index] = i
            
        print(f"Sensor {sensor_id} now mapped to Arduino pin {value}")
        print(f"Updated sensor mapping: {self.sensor_mapping}")
        
        # Send configuration to Arduino
        command = f"PIN:{sensor_id}:{pin_number}"
        if self.serial_thread:
            success = self.serial_thread.send_command(command)
            if success:
                self.status_label.setText(f"Status: Sent pin configuration ({command})")
            else:
                self.status_label.setText(f"Status: Failed to send configuration")
        
        # Refresh ALL pin displays in the UI
        self.update_pin_display()
        
        # Log the update for debugging
        sensor_names = ["Foot Error Sensor", "Interface Sensor"]
        print(f"Updated UI: {sensor_names[sensor_id]} is now on Pin {pin_number}")
    
    def update_sensor_debounce(self, value, sensor_id):
        """Update the debounce time for a specific sensor"""
        self.debounce_times[sensor_id] = int(value)
        print(f"Debounce time for sensor {sensor_id} updated to {value}ms")
    
    def refresh_ports(self):
        """Refresh available serial ports"""
        self.port_combo.clear()
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.port_combo.addItem(port.device)
    
    def connect_disconnect(self):
        """Connect or disconnect serial port"""
        if self.serial_thread is None or not self.serial_thread.running:
            # Connect
            port = self.port_combo.currentText()
            baud_rate = int(self.baud_combo.currentText())
            
            if not port:
                self.status_label.setText("Status: No port selected")
                return
            
            self.serial_thread = SerialThread(port, baud_rate)
            self.serial_thread.data_received.connect(self.process_data)
            self.serial_thread.config_received.connect(self.process_config)
            self.serial_thread.start()
            
            self.connect_button.setText("Disconnect")
            self.status_label.setText(f"Status: Connecting to {port}")
            self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #FF9800;")
            
            # Add a small delay to simulate connecting, then update status
            QTimer.singleShot(2000, lambda: self.connection_successful(port))
            
            self.start_button.setEnabled(True)
            self.port_combo.setEnabled(False)
            self.baud_combo.setEnabled(False)
            self.refresh_button.setEnabled(False)
            self.arduino_connected = True
            
            # Enable pin configuration
            for combo in self.pin_combos:
                combo.setEnabled(True)
        else:
            # Disconnect
            self.serial_thread.stop()
            self.serial_thread = None
            
            self.connect_button.setText("Connect")
            self.status_label.setText("Status: Disconnected")
            self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #666;")
            
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(False)
            self.port_combo.setEnabled(True)
            self.baud_combo.setEnabled(True)
            self.refresh_button.setEnabled(True)
            self.arduino_connected = False
            
            # Disable pin configuration
            for combo in self.pin_combos:
                combo.setEnabled(False)
            
            # Stop recording if active
            if self.is_recording:
                self.stop_trial()
    
    def connection_successful(self, port):
        """Update status when connection is successful"""
        self.status_label.setText(f"Status: Connected to {port}")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #4CAF50;")
    
    def process_config(self, config_data):
        """Process configuration data from Arduino"""
        print(f"Received configuration: {config_data}")
        
        # Flag to track if we made changes
        changes_made = False
        
        if "config" in config_data and isinstance(config_data["config"], list):
            for item in config_data["config"]:
                if "index" in item and "pin" in item:
                    index = item["index"]
                    pin = item["pin"]
                    
                    if 0 <= index < self.NUM_SENSORS:
                        # Check if there's an actual change
                        if self.arduino_pins[index] != pin:
                            changes_made = True
                            
                        # Update the UI to reflect Arduino's current configuration
                        self.arduino_pins[index] = pin
                        
                        # Update combobox without triggering signal
                        self.pin_combos[index].blockSignals(True)
                        self.pin_combos[index].setCurrentText(str(pin))
                        self.pin_combos[index].blockSignals(False)
                        
                        # Update mapping
                        pin_index = pin - 2
                        self.sensor_mapping[pin_index] = index
                        
                        # Log the change
                        sensor_names = ["Foot Error Sensor", "Interface Sensor"]
                        print(f"Configuration update: {sensor_names[index]} is now on Pin {pin}")
            
            # Force UI update even if no apparent changes were made, this ensures UI is updated on initial connection
            self.update_pin_display()
            if changes_made:
                self.status_label.setText(f"Status: Updated pin configuration from Arduino")
                print("Pin configuration was changed - UI updated")
            else:
                print("No pin configuration changes detected - UI updated anyway")
    
    def start_trial(self):
        """Start a new trial"""
        self.trial_count += 1
        self.start_time = time.time()
        self.end_time = None
        self.is_recording = True
        self.current_trial_data = []
        
        # Reset sensor counts
        self.sensor_counts = [0, 0]  # Only 2 sensors now
        for i in range(self.NUM_SENSORS):
            self.count_labels[i].setText("Trigger Count: 0")
        
        # Reset debounce timers
        self.last_trigger_time = [0, 0]  # Only 2 sensors now
        
        # Update trial time display
        self.timer_label.setText("Trial Time: 0.00s")
        
        # Start timer to update the trial time display
        self.trial_timer.start()
        
        # Display current debounce settings and pin configuration
        debounce_info = ", ".join([f"S{i+1}(Pin {self.arduino_pins[i]}): {self.debounce_times[i]}ms" for i in range(self.NUM_SENSORS)])
        print(f"Trial {self.trial_count} started with settings: {debounce_info}")
        
        # Format start time for display
        formatted_start_time = datetime.fromtimestamp(self.start_time).strftime('%Y-%m-%d %H:%M:%S')
        print(f"Trial started at: {formatted_start_time}")
        
        # Clear chart including any end-trial marker lines
        self.plot_widget.clear()
        
        # Reset event line storage
        self.line_items = [[], []]
        self.event_lines = [[], []]
        
        # Update status
        self.status_label.setText("Status: Recording")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #4CAF50;")
            
        # Make sure all UI is updated with current pin configuration
        self.update_pin_display()
        
        self.trial_label.setText(f"Current Trial: {self.trial_count}")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
    
    def stop_trial(self):
        """End current trial"""
        if not self.is_recording:
            return
        
        # Record end time
        self.end_time = time.time()
        self.is_recording = False
        
        # Stop the trial timer
        self.trial_timer.stop()
        
        # Calculate total trial duration
        trial_duration = self.end_time - self.start_time
        
        # Update the timer display with final time
        self.timer_label.setText(f"Trial Time: {trial_duration:.2f}s")
        
        # Format end time for display
        formatted_end_time = datetime.fromtimestamp(self.end_time).strftime('%Y-%m-%d %H:%M:%S')
        print(f"Trial ended at: {formatted_end_time}")
        print(f"Trial duration: {trial_duration:.2f} seconds")
        
        # Save current trial data
        trial_summary = {
            "trial_number": self.trial_count,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": trial_duration,
            "sensor_counts": self.sensor_counts.copy(),
            "events": self.current_trial_data.copy()
        }
        
        self.all_trials_data.append(trial_summary)
        
        # Update status
        self.status_label.setText("Status: Trial Completed")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #FF9800;")
        
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.trial_label.setText(f"Last Trial: {self.trial_count} (Completed)")
        
        # Add a line to mark the end of the trial with enhanced styling
        self.end_trial_line = pg.InfiniteLine(
            pos=trial_duration, 
            angle=90, 
            pen=pg.mkPen('#FF5555', width=2, style=Qt.DashLine),
            label=f"End: {trial_duration:.2f}s",
            labelOpts={'position': 0.9, 'color': (200, 0, 0), 'fill': (255, 255, 255, 70)}
        )
        self.plot_widget.addItem(self.end_trial_line)
    
    def process_data(self, data):
        """Process data from Arduino with individual sensor debounce logic"""
        try:
            debug_info = f"Received data: {data}"
            self.debug_label.setText(debug_info)
            
            # Expected format is JSON: {"sensor": 0, "state": 1}
            sensor_data = json.loads(data)
            arduino_sensor_id = sensor_data.get("sensor")
            state = sensor_data.get("state")
            
            if arduino_sensor_id is None or state is None:
                return
            
            # Only process pins that are in our mapping
            if arduino_sensor_id not in self.sensor_mapping:
                print(f"Ignored data from unmapped Arduino pin index {arduino_sensor_id}")
                return
                
            # Map Arduino pin index to our sensor index
            sensor_id = self.sensor_mapping[arduino_sensor_id]
            
            # Only process sensor trigger events (state is 1)
            if self.is_recording and state == 1:
                current_time = time.time() - self.start_time
                current_time_ms = int(current_time * 1000)  # Convert to milliseconds
                
                # Apply debounce logic with sensor-specific debounce time
                last_trigger = self.last_trigger_time[sensor_id]
                if current_time_ms - last_trigger < self.debounce_times[sensor_id]:
                    print(f"Debounce: Ignored trigger for sensor {sensor_id} "
                          f"(time since last: {current_time_ms - last_trigger}ms, "
                          f"debounce setting: {self.debounce_times[sensor_id]}ms)")
                    return
                
                # Update last trigger time
                self.last_trigger_time[sensor_id] = current_time_ms
                
                # Record event
                event = {
                    "sensor": sensor_id,
                    "time": current_time
                }
                self.current_trial_data.append(event)
                
                # Update count
                self.sensor_counts[sensor_id] += 1
                self.count_labels[sensor_id].setText(f"Trigger Count: {self.sensor_counts[sensor_id]}")
                
                # Add to chart data - create vertical line at event time
                sensor_name = "Foot Error Sensor" if sensor_id == 0 else "Interface Sensor"
                print(f"Trigger recorded for {sensor_name} at {current_time:.3f}s")
                
                # Create vertical line with nicer colors
                colors = [pg.mkPen(color="#e74c3c", width=2), pg.mkPen(color="#3498db", width=2)]
                line = VerticalLineItem(
                    x=current_time,
                    y=sensor_id,
                    height=0.6,  # line height
                    width=2,     # line width
                    color=colors[sensor_id]
                )
                self.plot_widget.addItem(line)
                self.line_items[sensor_id].append(line)
                
        except Exception as e:
            print(f"Data processing error: {e}")
            self.debug_label.setText(f"Error: {str(e)}")
    
    def update_plot(self):
        """Update chart - minimal implementation as we use direct line addition"""
        # This method is still called by the timer but doesn't need
        # to do much since we add vertical lines directly in process_data
        pass
    
    def save_data(self):
        """Save all trial data to CSV"""
        if not self.all_trials_data:
            return
            
        try:
            # Choose save file
            file_path, _ = QFileDialog.getSaveFileName(self, "Save Data", "", "CSV Files (*.csv)")
            
            if not file_path:
                return
                
            with open(file_path, 'w', newline='') as file:
                writer = csv.writer(file)
                
                # Write header row with relative time columns
                writer.writerow([
                    "Trial", 
                    "Trial_Start_Time",  # Absolute start time for reference
                    "Trial_Duration",    # Total duration in seconds
                    "Sensor", 
                    "Event_Time",        # Time relative to trial start in seconds
                    "Foot_Error_Count", 
                    "Interface_Sensor_Count"
                ])
                
                # Write data
                for trial in self.all_trials_data:
                    trial_num = trial["trial_number"]
                    counts = trial["sensor_counts"]
                    # Keep absolute start time for reference
                    start_time_str = datetime.fromtimestamp(trial["start_time"]).strftime('%Y-%m-%d %H:%M:%S')
                    duration = trial["duration"]
                    
                    # First write a row for the trial start (no sensor event)
                    writer.writerow([
                        trial_num,
                        start_time_str,
                        f"{duration:.2f}",
                        "START",
                        "0.00",
                        counts[0],
                        counts[1]
                    ])
                    
                    # Write rows for each sensor event
                    for event in trial["events"]:
                        sensor_id = event["sensor"]
                        sensor_name = "Foot Error Sensor" if sensor_id == 0 else "Interface Sensor"
                        event_time = event["time"]  # Already relative to trial start
                        
                        writer.writerow([
                            trial_num,
                            start_time_str,
                            f"{duration:.2f}",
                            sensor_name,
                            f"{event_time:.4f}",
                            counts[0],
                            counts[1]
                        ])
                    
                    # Last write a row for the trial end (no sensor event)
                    writer.writerow([
                        trial_num,
                        start_time_str,
                        f"{duration:.2f}",
                        "END",
                        f"{duration:.2f}",
                        counts[0],
                        counts[1]
                    ])
            
            self.status_label.setText(f"Status: Data saved to {file_path}")
            self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #4CAF50;")
        except Exception as e:
            self.status_label.setText(f"Status: Save failed - {e}")
            self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #f44336;")
    
    def closeEvent(self, event):
        if self.serial_thread and self.serial_thread.running:
            self.serial_thread.stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SensorVisualizationApp()
    window.show()
    sys.exit(app.exec_())

