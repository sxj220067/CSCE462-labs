#include <wiringPi.h>
#include <stdio.h>
#include <stdint.h>

// ---- global variables your function depends on ----
volatile uint32_t *gpioBase;
int pin = 0;

// ---- dummy implementations if your lab requires them ----
// (replace these with your lab's real versions if provided)
void setPinOn(volatile uint32_t *base, int p) {
    digitalWrite(p, HIGH);
}

void setPinOff(volatile uint32_t *base, int p) {
    digitalWrite(p, LOW);
}

// ---- your function (UNCHANGED) ----
void squareWave(){
    while(1){
        setPinOn(gpioBase,pin);
        delayMicroseconds(5);
        setPinOff(gpioBase,pin);
        delayMicroseconds(5);
    }
}

// ---- main ----
int main(void){
    wiringPiSetup();        // init wiringPi
    pinMode(pin, OUTPUT);  // set GPIO as output

    squareWave();           // run forever
    return 0;
}
// // !!optional!!
// #include <wiringPi.h>
// #include <stdio.h>
// #include <unistd.h>
// #define outputPin 0
// #define C4 261.6 //Hz
// #define period 1 //second

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
//     while(1){
//         run();
//     }
// }


