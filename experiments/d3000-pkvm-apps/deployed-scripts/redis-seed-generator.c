#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void usage(const char *prog)
{
    fprintf(stderr, "usage: %s START COUNT VALUE_BYTES\n", prog);
    exit(2);
}

int main(int argc, char **argv)
{
    char *end;
    uint64_t start, count, i;
    size_t value_bytes;
    char *value;

    if (argc != 4)
        usage(argv[0]);
    errno = 0;
    start = strtoull(argv[1], &end, 10);
    if (errno || *end)
        usage(argv[0]);
    count = strtoull(argv[2], &end, 10);
    if (errno || *end)
        usage(argv[0]);
    value_bytes = strtoull(argv[3], &end, 10);
    if (errno || *end || value_bytes == 0)
        usage(argv[0]);

    value = malloc(value_bytes);
    if (!value) {
        perror("malloc");
        return 1;
    }
    for (size_t j = 0; j < value_bytes; j++)
        value[j] = "0123456789abcdef"[(j + start) & 15];

    setvbuf(stdout, NULL, _IOFBF, 1 << 20);
    for (i = start; i < start + count; i++) {
        char key[64];
        int key_len = snprintf(key, sizeof(key), "k:%" PRIu64, i);
        if (printf("*3\r\n$3\r\nSET\r\n$%d\r\n%s\r\n$%zu\r\n", key_len, key,
                   value_bytes) < 0 || fwrite(value, value_bytes, 1, stdout) != 1 ||
            fwrite("\r\n", 2, 1, stdout) != 1) {
            perror("write");
            free(value);
            return 1;
        }
    }
    free(value);
    return fflush(stdout) == 0 ? 0 : 1;
}

