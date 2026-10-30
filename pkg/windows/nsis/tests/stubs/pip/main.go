// Record installer hook calls without downloading or installing dependencies.
package main

import (
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
)

func main() {
	executable, err := os.Executable()
	if err != nil {
		panic(err)
	}
	state, err := exec.Command(filepath.Join(filepath.Dir(executable), "ssm.exe"), "status", "salt-minion").Output()
	if err != nil {
		panic(err)
	}
	log, err := os.OpenFile(os.Getenv("NSIS_TEST_PIP_LOG"), os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0600)
	if err != nil {
		panic(err)
	}
	err = json.NewEncoder(log).Encode(map[string]interface{}{
		"executable": executable,
		"args":       os.Args[1:],
		"config_dir": os.Getenv("SALT_CONFIG_DIR"),
		"service":    strings.TrimSpace(string(state)),
	})
	if err != nil {
		panic(err)
	}
	if err := log.Close(); err != nil {
		panic(err)
	}
	exitCode, err := strconv.Atoi(os.Getenv("NSIS_TEST_PIP_EXIT"))
	if err != nil {
		panic(err)
	}
	os.Exit(exitCode)
}
