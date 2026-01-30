
// squareWave()
// freq = 100 kHz(1/(5+5us))

void squareWave(){
    while(1){
        setPinOn(gpioBase,pin);
        delayMicroseconds(5);
        setPinOff(gpioBase,pin);
        delayMicroseconds(5);
    }
}



// !!optional!!
// include <wiringPi.h>
// include <stdio.h>
// define outputPin 0
// define C4 261.6 //Hz
// define period 1 //second

void tone(){
    long half_cycle = (long)(1000000/(2*C4));
    long numberOfloops = (long)(freq*period);
    for(int i = 0; i < numberOfloops;i++){
        setPinOn(gpioBase,outputPin);
        delayMicroseconds(half_cycle);
        setPinOff(gpioBase, outputPin);
        delayMicroseconds(half_cycle);
    }
}
void run(){
    tone();
    delay(20);
}

int main(){
    //set up gpio. TImer,etc. here
    while(1){
        run();
    }
}


