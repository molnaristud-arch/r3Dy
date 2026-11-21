#include "Arduino.h"
unsigned long simUs=0; int pins[20]; int beeps=0; std::string out; std::deque<char> in;
#include "sketch.inc"  // the .ino, copied here by run.sh
void run(double sec){ unsigned long end=simUs+(unsigned long)(sec*1e6); while(simUs<end){ loop(); simUs+=50; } }
void send(const char*s){ while(*s) in.push_back(*s++); in.push_back('\n'); }
int main(){
  pins[BUTTON_PIN]=HIGH; setup();
  // STEP mode: record position at every photo
  std::vector<long> at; int prevBeeps=0; send("s");
  unsigned long t0=simUs;
  while(mode!=IDLE || simUs-t0<1000){ loop(); simUs+=50; if(beeps!=prevBeeps){prevBeeps=beeps; at.push_back(position);} if(simUs-t0>600e6) break; }
  printf("photos=%zu  time=%.1fs  last_pos=%ld (%.2f deg)\n", at.size(), (simUs-t0)/1e6, at.back(), at.back()*360.0/STEPS_PER_REV);
  long mn=1e9,mx=0; for(size_t i=1;i<at.size();i++){ long d=at[i]-at[i-1]; mn=std::min(mn,d); mx=std::max(mx,d);} printf("step deltas %ld..%ld (%.3f..%.3f deg)\n",mn,mx,mn*360/STEPS_PER_REV,mx*360/STEPS_PER_REV);
  printf("coils off after finish: %d%d%d%d\n",pins[8],pins[9],pins[10],pins[11]);
  // CONT 1 RPM for 60 s
  send("c"); run(0.01); long p0=position; run(60); printf("CONT 60s: %ld steps = %.3f rev\n", position-p0, (position-p0)/STEPS_PER_REV);
  send("r2.5"); run(0.01); p0=position; run(60); printf("CONT r2.5 60s: %.3f rev\n",(position-p0)/STEPS_PER_REV);
  send("x"); run(0.01); p0=position; run(5); printf("after x moved: %ld\n", position-p0);
  // button press during step mode stops it
  send("n8"); send("d1000"); run(0.01); pins[BUTTON_PIN]=LOW; run(0.1); pins[BUTTON_PIN]=HIGH; run(3); printf("mode after button start: %d\n",mode);
  pins[BUTTON_PIN]=LOW; run(0.1); pins[BUTTON_PIN]=HIGH; run(0.1); printf("mode after 2nd press: %d\n",mode);
  send("zzz"); send("d5"); run(0.01);
  printf("---serial---\n%s", out.c_str()+ (out.size()>1400? out.size()-1400:0));
}
