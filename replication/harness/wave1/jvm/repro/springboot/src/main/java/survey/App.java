package survey;

import java.io.InputStream;
import java.util.Map;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;

import jakarta.servlet.http.HttpServletRequest;

@SpringBootApplication
@RestController
public class App {
    public static void main(String[] args) {
        SpringApplication.run(App.class, args);
    }

    @GetMapping("/health")
    public Map<String, Object> health() {
        return Map.of("ok", true);
    }

    @PostMapping("/upload")
    public Map<String, Object> upload(HttpServletRequest req) throws Exception {
        long total = 0;
        byte[] buf = new byte[8192];
        try (InputStream in = req.getInputStream()) {
            int n;
            while ((n = in.read(buf)) > 0) {
                total += n;
            }
        }
        return Map.of("len", total);
    }
}
