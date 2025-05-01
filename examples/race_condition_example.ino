// Example Arduino sketch with potential race conditions between interrupts

// Global variables that will be accessed by multiple interrupts
volatile int counter = 0;
volatile bool flag = false;
volatile uint16_t adc_value = 0;
volatile uint32_t timestamp = 0;

void setup() {
  Serial.begin(9600);
  
  // Set up timer interrupt 1 (higher priority)
  cli();  // Disable interrupts
  // Set up Timer1 for interrupt
  TCCR1A = 0;
  TCCR1B = 0;
  TCNT1 = 0;
  OCR1A = 15624;  // Set compare match register (1Hz at 16MHz)
  TCCR1B |= (1 << WGM12);  // CTC mode
  TCCR1B |= (1 << CS12) | (1 << CS10);  // 1024 prescaler
  TIMSK1 |= (1 << OCIE1A);  // Enable timer compare interrupt
  
  // Set up timer interrupt 2 (lower priority)
  TCCR2A = 0;
  TCCR2B = 0;
  TCNT2 = 0;
  OCR2A = 249;  // Set compare match register (250Hz at 16MHz)
  TCCR2A |= (1 << WGM21);  // CTC mode
  TCCR2B |= (1 << CS22) | (1 << CS21) | (1 << CS20);  // 1024 prescaler
  TIMSK2 |= (1 << OCIE2A);  // Enable timer compare interrupt
  
  // Set up ADC interrupt
  ADMUX = (1 << REFS0);  // Use AVcc as reference
  ADCSRA = (1 << ADEN) | (1 << ADIE) | (1 << ADPS2) | (1 << ADPS1) | (1 << ADPS0);  // Enable ADC, enable interrupt, set prescaler to 128
  
  sei();  // Enable interrupts
  
  // Start first ADC conversion
  ADCSRA |= (1 << ADSC);
}

void loop() {
  // Main loop - doesn't touch the shared variables directly
  // But we'll read them for demonstration
  Serial.print("Counter: ");
  Serial.print(counter);  // Race condition potential here!
  Serial.print(", Flag: ");
  Serial.print(flag ? "true" : "false");  // Race condition potential here!
  Serial.print(", ADC value: ");
  Serial.print(adc_value);  // Race condition potential here!
  Serial.print(", Timestamp: ");
  Serial.println(timestamp);  // Race condition potential here!
  
  delay(1000);
}

// Timer1 Compare A interrupt handler (higher priority)
ISR(TIMER1_COMPA_vect) {
  counter++;  // Write to counter
  timestamp = millis();  // Write to timestamp
  
  // This is a higher priority interrupt, can interrupt TIMER2_COMPA_vect
  // but not itself
}

// Timer2 Compare A interrupt handler (lower priority)
ISR(TIMER2_COMPA_vect) {
  if (counter > 10) {  // Read from counter
    flag = !flag;  // Write to flag
  }
  
  // Lower priority interrupt, can be interrupted by TIMER1_COMPA_vect
}

// ADC conversion complete interrupt handler
// This has the same priority as TIMER2 by default
ISR(ADC_vect) {
  // Read the ADC result
  adc_value = ADC;  // Write to adc_value
  
  // Start the next conversion
  ADCSRA |= (1 << ADSC);
  
  // Can be interrupted by TIMER1, but has the same priority as TIMER2
} 