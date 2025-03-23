// Arduino program for optical sensors detection
// Communicates with PC application via serial port

// Define constants
#define SERIAL_BAUD_RATE 9600

// Array of potential sensor pins (2-13) - will be configured from PC
const int MAX_SENSORS = 2;
int sensorPins[MAX_SENSORS] = {2, 3}; // Default pins
bool lastPinState[MAX_SENSORS] = {HIGH, HIGH}; // Default state (assuming sensors are active LOW)

// Configuration variables
bool configMode = false;
String inputString = "";
bool stringComplete = false;

void setup() {
  // Initialize serial communication
  Serial.begin(SERIAL_BAUD_RATE);
  
  // Reserve memory for input string
  inputString.reserve(200);
  
  // Initialize sensor pins
  for (int i = 0; i < MAX_SENSORS; i++) {
    pinMode(sensorPins[i], INPUT_PULLUP); // Use internal pull-up
    lastPinState[i] = digitalRead(sensorPins[i]);
  }
  
  // Send initial configuration to PC
  sendPinConfiguration();
}

void loop() {
  // Check for configuration commands
  if (stringComplete) {
    processCommand();
    inputString = "";
    stringComplete = false;
  }
  
  // Read sensors and send events
  for (int i = 0; i < MAX_SENSORS; i++) {
    bool currentState = digitalRead(sensorPins[i]);
    
    // Check for state change (from HIGH to LOW means sensor triggered)
    if (lastPinState[i] == HIGH && currentState == LOW) {
      // Send sensor event (index is the Arduino pin index 0-11 for pins 2-13)
      sendSensorEvent(sensorPins[i] - 2, 1); // State 1 means triggered
    } 
    else if (lastPinState[i] == LOW && currentState == HIGH) {
      // Optional: Send sensor release event
      sendSensorEvent(sensorPins[i] - 2, 0); // State 0 means released
    }
    
    lastPinState[i] = currentState;
  }
  

  delay(10);
}

// Process serial command received from PC
void processCommand() {
  // Command format: "PIN:index:pin_number". Example: "PIN:0:5" - Set first sensor to pin 5
  
  if (inputString.startsWith("PIN:")) {
    int firstColon = inputString.indexOf(':');
    int secondColon = inputString.indexOf(':', firstColon + 1);
    
    if (firstColon != -1 && secondColon != -1) {
      String indexStr = inputString.substring(firstColon + 1, secondColon);
      String pinStr = inputString.substring(secondColon + 1);
      
      int sensorIndex = indexStr.toInt();
      int pinNumber = pinStr.toInt();
      
      // Validate pin range (2-13 for digital pins)
      if (sensorIndex >= 0 && sensorIndex < MAX_SENSORS && 
          pinNumber >= 2 && pinNumber <= 13) {
        
        // First set pin to input to avoid conflicts
        pinMode(sensorPins[sensorIndex], INPUT);
        
        // Update pin mapping
        sensorPins[sensorIndex] = pinNumber;
        
        // Configure new pin
        pinMode(sensorPins[sensorIndex], INPUT_PULLUP);
        lastPinState[sensorIndex] = digitalRead(sensorPins[sensorIndex]);
        
        // Confirm configuration
        sendPinConfiguration();
      }
    }
  }
}

// Send sensor event to PC
void sendSensorEvent(int sensorPinIndex, int state) {
  // Format: {"sensor":pin_index,"state":state_value}
  Serial.print("{\"sensor\":");
  Serial.print(sensorPinIndex);
  Serial.print(",\"state\":");
  Serial.print(state);
  Serial.println("}");
}

// Send current pin configuration to PC
void sendPinConfiguration() {
  Serial.print("{\"config\":[");
  for (int i = 0; i < MAX_SENSORS; i++) {
    Serial.print("{\"index\":");
    Serial.print(i);
    Serial.print(",\"pin\":");
    Serial.print(sensorPins[i]);
    Serial.print("}");
    
    if (i < MAX_SENSORS - 1) {
      Serial.print(",");
    }
  }
  Serial.println("]}");
}

// Serial event handler - called when new data arrives
void serialEvent() {
  while (Serial.available()) {
    char inChar = (char)Serial.read();
    
    // Add character to input string
    inputString += inChar;
    
    // Process command on newline
    if (inChar == '\n') {
      stringComplete = true;
    }
  }
}