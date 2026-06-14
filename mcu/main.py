import pimd_mcu_302

# Always run
# pimd2.main()

# If connected via REPL, no auto start, execute manually.
# Otherwise runs automatically when the board powers up

if __name__ == "__main__":
    pimd_mcu_302.main()  # type: ignore
