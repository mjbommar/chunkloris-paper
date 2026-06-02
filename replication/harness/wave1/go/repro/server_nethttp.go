package main

import (
	"encoding/json"
	"io"
	"log"
	"net/http"
	_ "net/http/pprof"
)

func health(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte(`{"ok":true}`))
}

func upload(w http.ResponseWriter, r *http.Request) {
	b, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(map[string]int{"len": len(b)})
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("/health", health)
	mux.HandleFunc("/upload", upload)
	srv := &http.Server{Addr: ":8000", Handler: mux}
	go func() {
		log.Println("pprof on :6060")
		log.Println(http.ListenAndServe(":6060", nil))
	}()
	log.Println("listening on :8000")
	log.Fatal(srv.ListenAndServe())
}
