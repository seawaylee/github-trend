#!/bin/bash
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Project paths
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$PROJECT_DIR/venv"
CONFIG_FILE="$PROJECT_DIR/config/config.yaml"
CONFIG_EXAMPLE="$PROJECT_DIR/config/config.example.yaml"

# launchd paths
DAILY_PLIST="$HOME/Library/LaunchAgents/com.github-trend.daily.plist"
WEEKLY_PLIST="$HOME/Library/LaunchAgents/com.github-trend.weekly.plist"

echo -e "${GREEN}GitHub AI Trend Tracker - Setup${NC}\n"

# Function: Check Python version
check_python() {
    echo "Checking Python version..."

    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}✗ Python 3 not found${NC}"
        exit 1
    fi

    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    echo -e "${GREEN}✓ Python $PYTHON_VERSION found${NC}"
}

# Function: Create virtual environment
setup_venv() {
    if [ -d "$VENV_PATH" ]; then
        echo -e "${YELLOW}Virtual environment already exists${NC}"
    else
        echo "Creating virtual environment..."
        python3 -m venv "$VENV_PATH"
        echo -e "${GREEN}✓ Virtual environment created${NC}"
    fi

    # Activate venv
    source "$VENV_PATH/bin/activate"

    # Install dependencies
    echo "Installing dependencies..."
    pip install -q --upgrade pip
    pip install -q -r "$PROJECT_DIR/requirements.txt"
    echo -e "${GREEN}✓ Dependencies installed${NC}"
}

# Function: Setup configuration
setup_config() {
    if [ -f "$CONFIG_FILE" ]; then
        echo -e "${YELLOW}Config file already exists${NC}"
    else
        echo "Creating config file..."
        cp "$CONFIG_EXAMPLE" "$CONFIG_FILE"
        echo -e "${GREEN}✓ Config file created at $CONFIG_FILE${NC}"
        echo -e "${YELLOW}⚠ Please edit config/config.yaml with your settings${NC}"
    fi
}

# Function: Initialize database
init_database() {
    echo "Initializing database..."
    source "$VENV_PATH/bin/activate"
    python "$PROJECT_DIR/main.py" --init-db
    echo -e "${GREEN}✓ Database initialized${NC}"
}

# Function: Install launchd tasks
install_launchd() {
    echo "Installing launchd tasks..."

    # Create daily task plist
    cat > "$DAILY_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.github-trend.daily</string>
    <key>ProgramArguments</key>
    <array>
        <string>$VENV_PATH/bin/python</string>
        <string>$PROJECT_DIR/main.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>10</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/logs/daily.log</string>
    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/logs/daily.error.log</string>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
</dict>
</plist>
EOF

    # Create weekly task plist
    cat > "$WEEKLY_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.github-trend.weekly</string>
    <key>ProgramArguments</key>
    <array>
        <string>$VENV_PATH/bin/python</string>
        <string>$PROJECT_DIR/weekly.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>5</integer>
        <key>Hour</key>
        <integer>16</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/logs/weekly.log</string>
    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/logs/weekly.error.log</string>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
</dict>
</plist>
EOF

    # Load launchd tasks
    launchctl unload "$DAILY_PLIST" 2>/dev/null || true
    launchctl unload "$WEEKLY_PLIST" 2>/dev/null || true

    launchctl load "$DAILY_PLIST"
    launchctl load "$WEEKLY_PLIST"

    echo -e "${GREEN}✓ Launchd tasks installed${NC}"
    echo -e "  Daily task: Every day at 10:00"
    echo -e "  Weekly task: Every Friday at 16:00"
}

# Function: Uninstall launchd tasks
uninstall_launchd() {
    echo "Uninstalling launchd tasks..."

    launchctl unload "$DAILY_PLIST" 2>/dev/null || true
    launchctl unload "$WEEKLY_PLIST" 2>/dev/null || true

    rm -f "$DAILY_PLIST"
    rm -f "$WEEKLY_PLIST"

    echo -e "${GREEN}✓ Launchd tasks uninstalled${NC}"
}

# Function: Run tests
run_tests() {
    echo "Running tests..."
    source "$VENV_PATH/bin/activate"

    # Install pytest if not installed
    pip install -q pytest

    pytest "$PROJECT_DIR/tests" -v

    echo -e "${GREEN}✓ Tests passed${NC}"
}

# Main menu
case "${1:-}" in
    install)
        check_python
        setup_venv
        setup_config
        init_database
        install_launchd
        echo -e "\n${GREEN}✓ Setup complete!${NC}"
        echo -e "\nNext steps:"
        echo -e "1. Edit config/config.yaml with your settings"
        echo -e "2. Test: python main.py --dry-run"
        echo -e "3. Check logs: tail -f logs/daily.log"
        ;;

    uninstall)
        uninstall_launchd
        echo -e "${GREEN}✓ Uninstall complete${NC}"
        ;;

    test)
        run_tests
        ;;

    *)
        echo "Usage: $0 {install|uninstall|test}"
        echo ""
        echo "Commands:"
        echo "  install    - Install and setup everything"
        echo "  uninstall  - Remove launchd tasks"
        echo "  test       - Run tests"
        exit 1
        ;;
esac
