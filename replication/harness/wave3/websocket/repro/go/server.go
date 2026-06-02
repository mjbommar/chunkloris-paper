// gorilla/websocket echo-count.
package main

import (
	"encoding/json"
	"net/http"
	"strconv"

	"github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
	ReadBufferSize:  4096,
	WriteBufferSize: 4096,
	CheckOrigin:     func(r *http.Request) bool { return true },
}

func health(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(200)
	_, _ = w.Write([]byte(`{"ok":true}`))
}

func wsHandler(w http.ResponseWriter, r *http.Request) {
	nStr := r.URL.Query().Get("n")
	if nStr == "" {
		nStr = "50000"
	}
	nExpected, err := strconv.Atoi(nStr)
	if err != nil {
		http.Error(w, "bad n", 400)
		return
	}
	c, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		return
	}
	defer c.Close()
	received := 0
	for received < nExpected {
		_, _, err := c.ReadMessage()
		if err != nil {
			return
		}
		received++
	}
	body, _ := json.Marshal(map[string]int{"frames": received})
	_ = c.WriteMessage(websocket.TextMessage, body)
}

func main() {
	http.HandleFunc("/health", health)
	http.HandleFunc("/ws", wsHandler)
	_ = http.ListenAndServe("0.0.0.0:8000", nil)
}
