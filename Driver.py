import logging
import unittest

if __name__ == '__main__':
    # Setup logging to stderr.
    # Use either WARN, DEBUG, ALL, ...
    logging.basicConfig(level=logging.WARN, format='(%(threadName)-10s) %(message)s')





    # Run tests with cmd line interface.
    # All tests: "python -m unittest -v test"
    # Class of tests: "python -m unittest -v test.MoreTests"
    # Specific test:
    #   "python -m unittest test.MoreTests.test_helloes_carry_plist_on"
    #unittest.main()