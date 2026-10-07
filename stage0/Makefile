CFLAGS = -O2 -g -Wall -Wno-unused-function -Wno-sign-compare -std=gnu11
SRC = util.c lex.c parse.c types.c check.c expr.c gen.c main.c
jot0: $(SRC) jot0.h check.h
	$(CC) $(CFLAGS) -o jot0 $(SRC)
clean:
	rm -f jot0
