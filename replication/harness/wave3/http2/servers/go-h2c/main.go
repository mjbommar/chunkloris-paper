package main

import (
	"encoding/json"
	"io"
	"log"
	"net/http"

	"golang.org/x/net/http2"
	"golang.org/x/net/http2/h2c"
)

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("content-type", "application/json")
		w.WriteHeader(200)
		_, _ = w.Write([]byte(`{"ok":true}`))
	})
	mux.HandleFunc("/upload", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" {
			w.WriteHeader(405)
			return
		}
		n, _ := io.Copy(io.Discard, r.Body)
		body, _ := json.Marshal(map[string]int64{"len": n})
		w.Header().Set("content-type", "application/json")
		w.WriteHeader(200)
		_, _ = w.Write(body)
	})

	h2s := &http2.Server{MaxConcurrentStreams: 1000}
	h := h2c.NewHandler(mux, h2s)
	srv := &http.Server{
		Addr:    "0.0.0.0:8000",
		Handler: h,
	}
	log.Println("go h2c listening on 0.0.0.0:8000")
	if err := srv.ListenAndServe(); err != nil {
		log.Fatal(err)
	}
}
