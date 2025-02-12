import subprocess
import time

def apply_netem(interface, delay="100ms", jitter="20ms", loss="0%"):
    """
    Applies network emulation (netem) settings on the given interface.
    
    :param interface: Network interface to apply netem on.
    :param delay: Base delay in milliseconds.
    :param jitter: Random variation in delay.
    :param loss: Packet loss percentage.
    """
    cmd = [
        "sudo", "tc", "qdisc", "add", "dev", interface, "root",
        "netem", "delay", delay, jitter, "loss", loss
    ]
    subprocess.run(cmd, check=True)
    print(f"Netem applied on {interface} with delay={delay}, jitter={jitter}, loss={loss}")

def remove_netem(interface):
    """
    Removes netem settings from the given network interface.
    
    :param interface: Network interface to remove netem from.
    """
    cmd = ["sudo", "tc", "qdisc", "del", "dev", interface, "root"]
    subprocess.run(cmd, check=True)
    print(f"Netem removed from {interface}")

def test_netem(interface, duration=10, delay="100ms", jitter="20ms", loss="0%"):
    """
    Applies netem, waits for a given duration, then removes it.
    
    :param interface: Network interface to apply netem on.
    :param duration: Duration to keep netem active before removing (in seconds).
    :param delay: Base delay in milliseconds.
    :param jitter: Random variation in delay.
    :param loss: Packet loss percentage.
    """
    try:
        apply_netem(interface, delay, jitter, loss)
        print(f"Netem active for {duration} seconds. Test your network now.")
        time.sleep(duration)
    finally:
        remove_netem(interface)

# Example usage:
# test_netem("eno33np0", duration=10, delay="200ms", jitter="50ms", loss="5%")
