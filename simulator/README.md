# Dummy CU SSH Simulator (PoC)

This directory contains a minimal Proof of Concept (PoC) to simulate an Airspan Control Unit (CU) over SSH. It allows developers to test the monitoring service without requiring access to physical CU hardware.

---

## 1. Supported Commands

The simulator supports the following commands:

* **`show rn status`**: Lists all connected Radio Nodes and their current states.
  ```
  RN1 ACTIVE
  RN2 ACTIVE
  ...
  ```
* **`show cells`**: Lists all cells and their configured PCIs.
  ```
  Cell1 PCI 101
  Cell2 PCI 102
  ...
  ```
* **`show uptime`**: Returns the Control Unit uptime.
  ```
  12 days
  ```
* **Any other command** will return:
  ```
  Unknown command
  ```

---

## 2. How to Run

### Command Line Simulator (`cu_simulator.py`)
This script can be executed in three ways:

1. **Interactive Shell**:
   Run the simulator without arguments to enter an interactive shell:
   ```bash
   python cu_simulator.py
   ```
   *Type `exit` or `quit` to exit.*

2. **One-off Execution**:
   Run a command by passing it as arguments:
   ```bash
   python cu_simulator.py show rn status
   ```
   Or using the `-c` flag:
   ```bash
   python cu_simulator.py -c "show rn status"
   ```

3. **SSH Forced Command Execution**:
   If SSH is configured to run the script automatically upon connection, it will read from the `SSH_ORIGINAL_COMMAND` environment variable.

### Periodic State Changer (`state_changer.py`)
To simulate real-time node transitions, run this script in the background. It randomly selects an RN and updates its state in `state.json` every 20 to 30 seconds:
```bash
python state_changer.py
```

---

## 3. SSH Configuration on the Ubuntu VM

To configure the Ubuntu VM to serve this simulator over SSH:

1. **Copy Files**:
   Copy the `simulator/` directory to the Ubuntu VM (e.g. `/home/simulator/`).

2. **Configure OpenSSH Server**:
   Ensure `openssh-server` is installed and running on the VM.

3. **Set Up forced commands or shell**:
   Choose one of the following methods to route incoming SSH commands to the simulator:
   
   * **Method A: Using `ForceCommand` (Recommended)**:
     Edit `/etc/ssh/sshd_config` (or `/etc/ssh/sshd_config.d/`) to restrict a specific user to the simulator:
     ```text
     Match User cu-monitor
         ForceCommand python3 /home/simulator/cu_simulator.py
     ```
     Restart the SSH daemon:
     ```bash
     sudo systemctl restart ssh
     ```

   * **Method B: Set as User's Shell**:
     Make `cu_simulator.py` executable (`chmod +x cu_simulator.py`) and set it as the default shell for the monitor user:
     ```bash
     sudo chsh -s /home/simulator/cu_simulator.py cu-monitor
     ```

---

## 4. Monitoring Service Integration

The monitoring service should connect to the dummy CU VM using the Paramiko SSH client.

### Connection Parameters
* **Host/IP**: `YOUR_VM_STATIC_IP` (configured manually)
* **Port**: `22` (default SSH port)
* **Username**: `cu-monitor` (or whichever user you configured on the VM)
* **Password**: `YOUR_SSH_PASSWORD` (or SSH Key authentication)

### Monitoring Workflow
```text
Monitoring Service (Paramiko Client)
  ├── 1. Connects to VM using configured SSH credentials
  ├── 2. Sends command (e.g. "show rn status")
  ├── 3. Receives simulator output
  ├── 4. Parses the output 
  └── 5. Updates the in-memory state and frontend
```
