package main

import (
	"io"
	"log"
	"net/http"
	_ "net/http/pprof"

	"github.com/gin-gonic/gin"
)

func main() {
	gin.SetMode(gin.ReleaseMode)
	r := gin.New()
	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"ok": true})
	})
	r.POST("/upload", func(c *gin.Context) {
		b, err := io.ReadAll(c.Request.Body)
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}
		c.JSON(http.StatusOK, gin.H{"len": len(b)})
	})
	go func() {
		log.Println("pprof on :6060")
		log.Println(http.ListenAndServe(":6060", nil))
	}()
	log.Println("gin listening on :8000")
	log.Fatal(r.Run(":8000"))
}
