int a = 0;
int b = 0;
int c = 0;

int foo(int k) {
  int n = a + k; // read from a
  b = n + 1; // write to b
  return n;
}

void attachInterrupt(int (*f)(int)) {
  // attach interrupt
}

int main() {
  attachInterrupt(&foo);
  int k = a + 1; // read from a
  a = k + 1; // write to a
  c = foo(c); // function call and read from c and write to c
  k = b + 1; // read from b
  b = k + 1; // write to b
  return 0;
}
