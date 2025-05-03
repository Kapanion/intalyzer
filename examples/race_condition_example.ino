// Simple race condition example using attachInterrupt
// Demonstrates a race condition between two interrupts accessing shared variables

// Shared variables that will be accessed by multiple interrupts
volatile int counter = 0;
volatile bool flag = false;

// Pin definitions
const int BUTTON_PIN = 2;  // Interrupt pin for button
const int LED_PIN = 13;    // LED pin for visual feedback

void setup() {
  Serial.begin(9600);
  
  // Set up pins
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(LED_PIN, OUTPUT);
  
  // Attach interrupts
  // First interrupt - triggered on button press
  attachInterrupt(digitalPinToInterrupt(BUTTON_PIN), buttonInterrupt, FALLING);
}

void loop() {
  // Main loop - read shared variables (potential race condition)
  Serial.print("Counter: ");
  Serial.print(counter);
  Serial.print(", Flag: ");
  Serial.println(flag ? "true" : "false");
  
  // Visual feedback
  digitalWrite(LED_PIN, flag);
  
  delay(1000);
}

// Button interrupt handler
void buttonInterrupt() {
  // This interrupt can be triggered at any time
  counter++;  // Increment counter
  flag = !flag;  // Toggle flag
}