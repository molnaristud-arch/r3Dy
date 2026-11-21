#pragma once
#include <cstdint>
#include <cstdlib>
#include <cstdio>
#include <string>
#include <deque>
#define HIGH 1
#define LOW 0
#define OUTPUT 1
#define INPUT_PULLUP 2
#define LED_BUILTIN 13
struct __FlashStringHelper;
#define F(s) ((const __FlashStringHelper*)(s))
extern unsigned long simUs; extern int pins[20]; extern int beeps; extern std::string out; extern std::deque<char> in;
inline unsigned long micros(){return simUs;} inline unsigned long millis(){return simUs/1000;}
inline void pinMode(int,int){} inline void digitalWrite(int p,int v){pins[p]=v;} inline int digitalRead(int p){return pins[p];}
inline void tone(int,int,unsigned long){beeps++;} inline void noTone(int){}
struct SerialT{ void begin(long){}
 void print(const char*s){out+=s;} void print(const __FlashStringHelper*s){out+=(const char*)s;}
 void print(char c){out+=c;} void print(int v){out+=std::to_string(v);} void print(long v){out+=std::to_string(v);} void print(unsigned long v){out+=std::to_string(v);}
 void print(float v,int d){char b[32];snprintf(b,32,"%.*f",d,v);out+=b;} void print(double v,int d){print((float)v,d);}
 template<class T> void println(T v){print(v);out+="\n";} void println(float v,int d){print(v,d);out+="\n";}
 int available(){return in.size();} char read(){char c=in.front();in.pop_front();return c;} } Serial;
