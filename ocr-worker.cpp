#include <iostream>
#include <vector>
#include <string>
#include <unordered_map>
#include <fstream>
#include <algorithm>
#include <cctype>
#include <iomanip>
#include <sstream>
#include <opencv2/opencv.hpp>
#include <tesseract/baseapi.h>
#include <leptonica/allheaders.h>
#include <nlohmann/json.hpp>

#ifdef _WIN32
#include <io.h>
#include <fcntl.h>
#endif

using json = nlohmann::json;

// --- EMBEDDED LIGHTWEIGHT SHA-256 ENGINE (Removes OpenSSL Dependency) ---
class NativeSha256 {
private:
    uint32_t state[8];
    uint32_t data_len;
    uint64_t bit_len;
    uint8_t buffer[64];

    void transform() {
        uint32_t maj, xorA, ch, xorB, sum, t1, t2, w[64];
        for (int i = 0; i < 16; i++) w[i] = (buffer[i * 4] << 24) | (buffer[i * 4 + 1] << 16) | (buffer[i * 4 + 2] << 8) | (buffer[i * 4 + 3]);
        for (int i = 16; i < 64; i++) {
            uint32_t s0 = ((w[i-15] >> 7) | (w[i-15] << 25)) ^ ((w[i-15] >> 18) | (w[i-15] << 14)) ^ (w[i-15] >> 3);
            uint32_t s1 = ((w[i-2] >> 17) | (w[i-2] << 15)) ^ ((w[i-2] >> 19) | (w[i-2] << 13)) ^ (w[i-2] >> 10);
            w[i] = w[i-16] + s0 + w[i-7] + s1;
        }
        uint32_t a = state[0], b = state[1], c = state[2], d = state[3], e = state[4], f = state[5], g = state[6], h = state[7];
        static const uint32_t k[64] = {
            0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
            0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
            0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
            0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
            0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
            0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
            0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
            0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
        };
        for (int i = 0; i < 64; i++) {
            uint32_t s1 = ((e >> 6) | (e << 26)) ^ ((e >> 11) | (e << 21)) ^ ((e >> 25) | (e << 7));
            ch = (e & f) ^ (~e & g);
            t1 = h + s1 + ch + k[i] + w[i];
            uint32_t s0 = ((a >> 2) | (a << 30)) ^ ((a >> 13) | (a << 19)) ^ ((a >> 22) | (a << 10));
            maj = (a & b) ^ (a & c) ^ (b & c);
            t2 = s0 + maj;
            h = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2;
        }
        state[0] += a; state[1] += b; state[2] += c; state[3] += d;
        state[4] += e; state[5] += f; state[6] += g; state[7] += h;
    }

public:
    NativeSha256() {
        state[0] = 0x6a09e667; state[1] = 0xbb67ae85; state[2] = 0x3c6ef372; state[3] = 0xa54ff53a;
        state[4] = 0x510e527f; state[5] = 0x9b05688c; state[6] = 0x1f83d9ab; state[7] = 0x5be0cd19;
        data_len = 0; bit_len = 0;
    }

    void update(const uint8_t* data, size_t len) {
        for (size_t i = 0; i < len; i++) {
            buffer[data_len] = data[i]; data_len++;
            if (data_len == 64) { transform(); bit_len += 512; data_len = 0; }
        }
    }

    std::string finalize() {
        uint64_t i = data_len;
        if (data_len < 56) {
            buffer[i++] = 0x80;
            while (i < 56) buffer[i++] = 0x00;
        } else {
            buffer[i++] = 0x80;
            while (i < 64) buffer[i++] = 0x00;
            transform(); memset(buffer, 0, 56);
        }
        bit_len += data_len * 8;
        buffer[63] = bit_len; buffer[62] = bit_len >> 8; buffer[61] = bit_len >> 16; buffer[60] = bit_len >> 24;
        buffer[59] = bit_len >> 32; buffer[58] = bit_len >> 40; buffer[57] = bit_len >> 48; buffer[56] = bit_len >> 56;
        transform();
        std::stringstream ss;
        for (int i = 0; i < 8; i++) ss << std::setw(8) << std::setfill('0') << state[i];
        return ss.str();
    }
};

// --- CORE UTILITIES ---
std::string normalize_name(const std::string& str) {
    std::string out;
    for (char c : str) { if (std::isalnum(c)) out += std::tolower(c); }
    return out;
}

int levenshtein(const std::string& s1, const std::string& s2) {
    const size_t m(s1.size()), n(s2.size());
    if (m == 0) return n; if (n == 0) return m;
    std::vector<int> costs(n + 1);
    for (size_t k = 0; k <= n; k++) costs[k] = k;
    size_t i = 0;
    for (char c1 : s1) {
        costs[0] = ++i; size_t corner = i - 1; size_t j = 0;
        for (char c2 : s2) {
            size_t upper = costs[j + 1];
            if (c1 == c2) costs[j + 1] = corner;
            else costs[j + 1] = std::min({costs[j], (int)upper, (int)corner}) + 1;
            corner = upper; j++;
        }
    }
    return costs[n];
}

class OcrEngine {
private:
    std::unordered_map<std::string, std::string> poke_db;
    std::unordered_map<std::string, std::string> sha256_db;
    tesseract::TessBaseAPI* tess_psm6;
    tesseract::TessBaseAPI* tess_psm11;

public:
    OcrEngine() {
        load_databases();
        tess_psm6 = new tesseract::TessBaseAPI();
        tess_psm11 = new tesseract::TessBaseAPI();
        
        if (tess_psm6->Init(NULL, "PTOCR") || tess_psm11->Init(NULL, "PTOCR")) {
            std::cerr << "CRITICAL: Tesseract Init Failed (Verify PTOCR.traineddata exists)\n";
            exit(1);
        }
        tess_psm6->SetVariable("tessedit_char_whitelist", "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-");
        tess_psm11->SetVariable("tessedit_char_whitelist", "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-");
        tess_psm6->SetPageSegMode(tesseract::PSM_SINGLE_BLOCK);
        tess_psm11->SetPageSegMode(tesseract::PSM_SPARSE_TEXT);
    }

    ~OcrEngine() {
        tess_psm6->End(); tess_psm11->End();
        delete tess_psm6; delete tess_psm11;
    }

    void load_databases() {
        std::ifstream poke_file("pokenames.txt");
        if (poke_file.is_open()) {
            std::string line;
            while (std::getline(poke_file, line)) {
                if (!line.empty()) poke_db[normalize_name(line)] = line;
            }
        }
        std::ifstream json_file("post-training-data.json");
        if (json_file.is_open()) {
            try {
                json j; json_file >> j;
                for (auto& el : j.items()) sha256_db[el.key()] = el.value();
            } catch (...) {}
        }
    }

    std::string get_best_match(const std::string& extracted) {
        std::string norm = normalize_name(extracted);
        if (norm.empty()) return "NULL";
        if (poke_db.find(norm) != poke_db.end()) return poke_db[norm];

        std::string best_match = "NULL";
        int best_score = 999;
        for (const auto& pair : poke_db) {
            int score = levenshtein(norm, pair.first);
            if (score < best_score && score <= 3) {
                best_score = score; best_match = pair.second;
            }
        }
        return best_match;
    }

    std::string process_payload(const std::vector<uint8_t>& image_bytes) {
        NativeSha256 hasher;
        hasher.update(image_bytes.data(), image_bytes.size());
        std::string img_hash = hasher.finalize();

        if (sha256_db.find(img_hash) != sha256_db.end()) {
            return "CACHE_HIT|" + sha256_db[img_hash];
        }

        cv::Mat img = cv::imdecode(image_bytes, cv::IMREAD_COLOR);
        if (img.empty()) return "ERROR|DECODE_FAIL";

        // Performance Optimization: Crop/Blank configuration card text regions
        cv::rectangle(img, cv::Point(img.cols - 80, 0), cv::Point(img.cols, 75), cv::Scalar(255, 255, 255), cv::FILLED);
        cv::cvtColor(img, img, cv::COLOR_BGR2GRAY);
        cv::threshold(img, img, 127, 255, cv::THRESH_BINARY);

        // Core Strategy Layer 1 (PSM 6)
        tess_psm6->SetImage(img.data, img.cols, img.rows, 1, img.step);
        char* out6 = tess_psm6->GetUTF8Text();
        std::string res6(out6); delete[] out6;
        std::string extracted = res6.substr(0, res6.find('\n'));
        std::string match = get_best_match(extracted);

        if (match != "NULL") return "OCR_MATCH|" + match;

        // Fallback Strategy Layer 2 (PSM 11)
        tess_psm11->SetImage(img.data, img.cols, img.rows, 1, img.step);
        char* out11 = tess_psm11->GetUTF8Text();
        std::string res11(out11); delete[] out11;
        extracted = res11.substr(0, res11.find('\n'));
        match = get_best_match(extracted);

        if (match != "NULL") return "OCR_MATCH|" + match;
        return "FAIL|NO_MATCH";
    }
};

int main() {
#ifdef _WIN32
    _setmode(_fileno(stdin), _O_BINARY);
    _setmode(_fileno(stdout), _O_BINARY);
#endif
    std::ios_base::sync_with_stdio(false);
    std::cin.tie(NULL);

    OcrEngine engine;

    while (true) {
        uint32_t payload_size = 0;
        if (!std::cin.read(reinterpret_cast<char*>(&payload_size), sizeof(payload_size))) break;

        std::vector<uint8_t> buffer(payload_size);
        if (!std::cin.read(reinterpret_cast<char*>(buffer.data()), payload_size)) break;

        std::string result = engine.process_payload(buffer);
        std::cout << result << "\n";
        std::cout.flush();
    }
    return 0;
}
