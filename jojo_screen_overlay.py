"""Legacy entry point for the native desktop interface."""
def launch(fullscreen=False):
    from jojo_desktop import main
    main()

if __name__ == "__main__":
    launch()
