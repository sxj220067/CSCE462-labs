#include <wiringPi.h>
#include <stdio.h>
#include <stdint.h>

//global variable
volatile uint32_t *gpioBase;
int pin = 0;

void setPinOn(volatile uint32_t *base, int p) {
    digitalWrite(p, HIGH);
}

void setPinOff(volatile uint32_t *base, int p) {
    digitalWrite(p, LOW);
}

void squareWave(){
    while(1){
        setPinOn(gpioBase,pin);
        delayMicroseconds(5);
        setPinOff(gpioBase,pin);
        delayMicroseconds(5);
    }
}


int main(void){
    wiringPiSetup();       
    pinMode(pin, OUTPUT);  

    squareWave();           
    return 0;
}
// // !!optional!!
// #include <wiringPi.h>
// #include <stdio.h>
// #include <stdint.h>

// #define outputPin 0
// #define period 1 //second
// #define C4 261.6 //Hz
// #define freq 

// volatile uint32_t *gpioBase = 0;

// void setPinOn(volatile uint32_t *base, int p) {
//     digitalWrite(p, HIGH);
// }

// void setPinOff(volatile uint32_t *base, int p) {
//     digitalWrite(p, LOW);
// }
// void tone(){
//     long half_cycle = (long)(1000000/(2*C4));
//     long numberOfloops = (long)(freq*period);
//     for(int i = 0; i < numberOfloops;i++){
//         setPinOn(gpioBase,outputPin);
//         delayMicroseconds(half_cycle);
//         setPinOff(gpioBase, outputPin);
//         delayMicroseconds(half_cycle);
//     }
// }
// void run(){
//     tone();
//     delay(20);
// }

// int main(){
//     //set up gpio. TImer,etc. here
//     wiringPiSetup();
//     pinMode(outputPin, OUTPUT);
//     while(1){
//         run();
//     }
//     return 0;
// }


