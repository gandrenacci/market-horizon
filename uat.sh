#!/usr/bin/env bash
#
# UAT control script for Market Horizon.
#
# Market Horizon is a single Streamlit app, so each verb manages one service.
# Two interchangeable targets share the same verbs:
#   local  (default) — Streamlit via `uv run` on :8501
#   docker           — Streamlit via docker compose on :8501
#
#   ./uat.sh start [local|docker]      # start the app
#   ./uat.sh stop [local|docker]       # stop it
#   ./uat.sh restart [local|docker]    # stop then start
#   ./uat.sh status [local|docker]     # show whether it is running
#   ./uat.sh logs [local|docker]       # tail logs (Ctrl-C to exit)
#   ./uat.sh health [local|docker]     # probe the Streamlit health endpoint
#
# Local logs and PID files live under .uat/ (git-ignored); docker uses compose.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT/.uat"
APP_PORT=8501

mkdir -p "$RUN_DIR"

app_pid="$RUN_DIR/app.pid"
app_log="$RUN_DIR/app.log"

# --- helpers ---------------------------------------------------------------

is_running() {  # $1 = pidfile
  local pidfile="$1"
  [[ -f "$pidfile" ]] || return 1
  local pid
  pid="$(cat "$pidfile" 2>/dev/null || true)"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

# Poll the Streamlit health endpoint until it answers or we time out.
wait_for_health() {  # $1 = port  $2 = attempts
  local port="$1" attempts="${2:-30}"
  command -v curl >/dev/null 2>&1 || { sleep 2; return 0; }
  for _ in $(seq 1 "$attempts"); do
    if curl -fsS "http://localhost:$port/_stcore/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

probe_health() {  # $1 = name  $2 = port
  local name="$1" port="$2"
  if ! command -v curl >/dev/null 2>&1; then
    echo "· curl not found — cannot probe $name health" >&2
    return 1
  fi
  if curl -fsS "http://localhost:$port/_stcore/health" >/dev/null 2>&1; then
    echo "✓ $name healthy  http://localhost:$port"
  else
    echo "✗ $name not healthy on http://localhost:$port"
    return 1
  fi
}

# Start a command in its own process group so reloaders/children die together.
start_proc() {  # $1 = name  $2 = pidfile  $3 = logfile  $4 = workdir  $5 = command
  local name="$1" pidfile="$2" logfile="$3" workdir="$4" cmd="$5"
  if is_running "$pidfile"; then
    echo "✓ $name already running (pid $(cat "$pidfile"))"
    return 0
  fi
  echo "▶ starting $name ..."
  # setsid forks, so record the session leader's OWN pid ($$) from inside the
  # new session. That pid is the process-group id, so `kill -<pid>` later
  # signals Streamlit's child processes too. $cmd ends by exec'ing its
  # long-running process, so $$ stays the leader pid.
  ( cd "$workdir" && setsid bash -c 'echo $$ >"'"$pidfile"'"; '"$cmd" \
      >"$logfile" 2>&1 & )
  sleep 1
  if ! is_running "$pidfile"; then
    echo "✗ $name failed to start. Last log lines:"
    tail -n 20 "$logfile" || true
    return 1
  fi
  echo "✓ $name started (pid $(cat "$pidfile")) — logs: $logfile"
}

stop_proc() {  # $1 = name  $2 = pidfile
  local name="$1" pidfile="$2"
  if ! is_running "$pidfile"; then
    echo "· $name not running"
    rm -f "$pidfile"
    return 0
  fi
  local pid
  pid="$(cat "$pidfile")"
  echo "■ stopping $name (pid $pid) ..."
  # Negative pid -> signal the whole process group (started via setsid).
  kill -TERM "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
  for _ in $(seq 1 20); do
    is_running "$pidfile" || break
    sleep 0.25
  done
  if is_running "$pidfile"; then
    echo "  forcing kill ..."
    kill -KILL "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
  fi
  rm -f "$pidfile"
  echo "✓ $name stopped"
}

status_proc() {  # $1 = name  $2 = pidfile  $3 = url
  local name="$1" pidfile="$2" url="$3"
  if is_running "$pidfile"; then
    echo "✓ $name running (pid $(cat "$pidfile"))  $url"
  else
    echo "✗ $name stopped"
  fi
}

# --- local commands --------------------------------------------------------

local_start() {
  # --server.headless avoids the email prompt and browser auto-open in UAT.
  start_proc "app" "$app_pid" "$app_log" "$ROOT" \
    "exec uv run streamlit run app.py --server.port $APP_PORT --server.address 0.0.0.0 --server.headless true"
  echo
  if wait_for_health "$APP_PORT"; then
    echo "✓ app healthy"
  else
    echo "⚠ app started but health check did not pass yet — check: ./uat.sh logs"
  fi
  echo "App: http://localhost:$APP_PORT"
}

local_stop() {
  stop_proc "app" "$app_pid"
}

local_status() {
  status_proc "app" "$app_pid" "http://localhost:$APP_PORT"
}

local_logs() {
  echo "Tailing logs (Ctrl-C to exit)..."
  tail -n 30 -f "$app_log"
}

local_health() {
  probe_health "app" "$APP_PORT"
}

# --- docker commands -------------------------------------------------------

# Prefer the Compose v2 plugin, fall back to the legacy v1 binary.
compose() {
  if docker compose version >/dev/null 2>&1; then
    ( cd "$ROOT" && docker compose "$@" )
  elif command -v docker-compose >/dev/null 2>&1; then
    ( cd "$ROOT" && docker-compose "$@" )
  else
    echo "✗ docker compose not found. Install Docker with the Compose plugin." >&2
    return 1
  fi
}

docker_start() {
  echo "▶ building and starting docker stack ..."
  compose up -d --build
  echo
  if wait_for_health "$APP_PORT"; then
    echo "✓ app healthy"
  else
    echo "⚠ container started but health check did not pass yet — check: ./uat.sh logs docker"
  fi
  echo "App: http://localhost:$APP_PORT"
}

docker_stop() {
  echo "■ stopping docker stack ..."
  compose down
}

docker_status() {
  compose ps
}

docker_logs() {
  echo "Tailing docker logs (Ctrl-C to exit)..."
  compose logs -n 30 -f
}

docker_health() {
  probe_health "app" "$APP_PORT"
}

# --- dispatch --------------------------------------------------------------

cmd="${1:-}"
target="${2:-local}"

case "$target" in
  local|docker) ;;
  *)
    echo "Unknown target '$target'. Use 'local' or 'docker'." >&2
    exit 1
    ;;
esac

case "$cmd" in
  start)   "${target}_start" ;;
  stop)    "${target}_stop" ;;
  restart) "${target}_stop"; echo; "${target}_start" ;;
  status)  "${target}_status" ;;
  logs)    "${target}_logs" ;;
  health)  "${target}_health" ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|logs|health} [local|docker]"
    echo "       target defaults to 'local'"
    exit 1
    ;;
esac
