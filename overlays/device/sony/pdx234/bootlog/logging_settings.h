#ifndef YARP_LOGGING_SETTINGS_H
#define YARP_LOGGING_SETTINGS_H

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define YARP_SETTINGS_VERSION 0x00010010U
#define YARP_LOGGING_KEY "tw_metadata_logging"
#define YARP_LOGGING_PROPERTY "twrp.yarp.logging"

// -1 means the file is incomplete/unreadable. Do not override a saved "off"
// with a default until recovery has loaded its settings. A valid older settings
// file without the new key inherits the default "on".
static int yarp_logging_from_settings(FILE* file) {
    unsigned char header[4];
    if (fread(header, 1, sizeof(header), file) != sizeof(header)) return -1;
    uint32_t version = (uint32_t)header[0] | ((uint32_t)header[1] << 8) |
        ((uint32_t)header[2] << 16) | ((uint32_t)header[3] << 24);
    if (version != YARP_SETTINGS_VERSION) return -1;
    int enabled = 1;
    for (unsigned record = 0; record < 4096; ++record) {
        unsigned char length_bytes[2];
        size_t got = fread(length_bytes, 1, 2, file);
        if (got == 0 && feof(file) && !ferror(file)) return enabled;
        if (got != 2) return -1;
        size_t length = length_bytes[0] | ((size_t)length_bytes[1] << 8);
        char key[512], value[512];
        if (length == 0 || length >= sizeof(key) ||
            fread(key, 1, length, file) != length || key[length - 1] != '\0')
            return -1;
        const bool matches = length == sizeof(YARP_LOGGING_KEY) &&
            memcmp(key, YARP_LOGGING_KEY, sizeof(YARP_LOGGING_KEY)) == 0;
        if (fread(length_bytes, 1, 2, file) != 2) return -1;
        length = length_bytes[0] | ((size_t)length_bytes[1] << 8);
        if (length == 0 || length >= sizeof(value) ||
            fread(value, 1, length, file) != length || value[length - 1] != '\0')
            return -1;
        if (matches) {
            if (length != 2 || (value[0] != '0' && value[0] != '1')) return -1;
            enabled = value[0] == '1';
        }
    }
    return -1;
}
#endif
