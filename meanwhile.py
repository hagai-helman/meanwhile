"""Very Easy Multithreading.

If you want to call the same function on many inputs, in a multithreaded 
fashion, ```meanwhile``` makes it easy.

It can make your code significantly faster, especially if the function requires
I/O operations, like file access or HTTP(S) queries.

Simple Usage Example:

    Suppose you have a function named `test_url`, that gets a URL, downloads
    its content, and tests whether it contains the word "meanwhile". Also,
    suppose you have a file, named `urls.txt`, where each line contains a URL
    you would like to apply `test_url` to.

    You can do the following:

    >>> from meanwhile import Job
    >>> job = Job(test_url, 10)  # at most 10 threads will be used concurrently.
    >>> urls = open("urls.txt").read().splitlines()
    >>> job.add_many(urls)
    >>> job.wait()
    >>> results = job.get_results()

The target function (in the example: `test_url`) should get one argument, and
this argument should be hashable.

Note that if your function prints output, you probably want to use 
`meanwhile.print()` instead of Python's built-in `print()` function.
This function prevents conflicts both with other threads, and with the progress
updates shown by the `wait` method.

For the full documentation, see https://github.com/hagai-helman/meanwhile.
"""

from threading import Thread, Lock
from queue import Queue, Empty
from time import time, sleep
from random import choice

# Console Output And Printing
# ***************************
#
# The method Job.wait() provides progress updates by printing a status line. 
# Hence we need functions to overwrite status.
#
# The function meanwhile.print() is a wrapper for the builtin print() function
# that is more thread-safe, and also works well with the status printing
# feature.

# We stash the builtin print() function as meanwhile._print();

_print = print

# We use two global variables for printing:
# 1. _plock is a global print-lock;
# 2. _status contains the last status, and is used for both overwriting and
#    rewriting.

_plock = Lock()
_status = None

# _hide_status() and _show_status() are the two functions that handle
# writing and overwriting the status.

def _hide_status():
    """Remove previous status from screen.
    """

    # Overwrite previous status with whitespaces, and return cursor to the
    # beginning of the line.
    #
    # Note that each character is replaced with a ' ', except '\t' that
    # just moves the cursor.
    #
    # Some special characters, like '\n', are mishandled; That's OK, we
    # don't expect them to appear in status.

    global _status
    if _status is not None:
        space = ""
        for c in _status:
            if c == '\t':
                space += "\t"
            else:
                space += " "
        _print("\r" + space + "\r", end = "", flush = True)
    _status = None

def _show_status(status):
    """Replace the current status shown on screen with a new status.
    """
    global _status
    _hide_status()
    _print(status, end="", flush=True)
    _status = status

def print(*args, **kw):
    """A wrapper for the builtin print() function, which is more thread-safe
    and does not conflict with meanwhile's status lines.
    """
    with _plock:
        status = _status
        _hide_status()
        _print(*args, **kw)
        if status is not None:
            _show_status(status)

def _generate_tid():
    """Generate a random thread ID.
    """
    return ''.join((choice("0123456789abcdef") for i in range(16)))

class Job(object):
    def __init__(self, target, n_threads = 1, n_attempts = 1, factory = False):
        """Initialize a new Job object.

        Args:
            target - A target function or a target factory. 
                     A target function is a function that gets one arguent of
                     hashable type.
                     A target factory is a function that gets no arguments and
                     returns a target function (or, equivalently, a class for
                     which __init__ takes no arguments, and __call__ is a
                     target function).
                     The target function is the function that will be called
                     with each input as argument. If a target factory is given,
                     a target function will be created for each thread spawned.                     
            n_threads - An integer. The maximal number of threads to be used 
                        concurrently.
            n_attempts - An integer. The number of attempts for each input
                         before it is considered 'failed', and the exception
                         is stored in the exceptions' dictionary.
            factory - A boolean. Must be True if (and only if) the target
                      argument is a target factory.

        Note:
            All arguments of __init__ can be later changed by the setter 
            methods: Job.set_target, Job.set_n_threads, and
            Job.set_n_attempts.
        """

        # Initialize Object's Fields
        # **************************

        # The target function or target factory:

        self._target = (target, factory)

        # The queue of inputs to be processed:

        self._queue = Queue()

        # The set of all inputs ever added:

        self._inputs = set()

        # The dictionaries that store the results and the excpetions:

        self._results = {}
        self._exceptions = {}

        # Flow control configuration variables:

        self._n_attempts = n_attempts
        self._n_threads = n_threads

        # Thread management:

        self._threads = {}
        self._n_paused = 0

        # Locks:

        self._ilock = Lock()    # input set lock
        self._rlock = Lock()    # results lock
        self._elock = Lock()    # exceptions lock
        self._tlock = Lock()    # thread dict lock
        self._block = Lock()    # pause lock
        self._plock = Lock()    # paused threads counter lock

    def _start(self):
        """Spawn new threads as needed."""

        # We define `worker`, which will be the target of each thread.

        def worker(tid):

            # Initialize the thread's target_function, and memorize self._target.

            target = self._target
            if target[1]:
                target_function = target[0]()
            else:
                target_function = target[0]

            while True:

                # First, if the job is paused, we wait until it is resumed.
                # (If the job is paused, self._block will be locked.)

                with self._plock:
                    self._n_paused += 1
                with self._block:
                    pass
                with self._plock:
                    self._n_paused -= 1

                # Then, we check whether there are too many threads, and if
                # there are, we commit suicide.

                with self._tlock:
                    if len(self._threads) > self._n_threads:
                        del self._threads[tid]
                        return

                # If target has changed - reinitialize the thread's 
                # target_function.

                if self._target != target:
                    target = self._target
                    if target[1]:
                        target_function = target[0]()
                    else:
                        target_function = target[0]

                # Finally, we try to get an input of the queue, and process
                # it.

                try:
                    (arg, attempt) = self._queue.get(timeout = 1)
                    result = target_function(arg)
                    with self._rlock:
                        self._results[arg] = result
                except Empty:
                    with self._tlock:
                        del self._threads[tid]
                    return
                except Exception as e:
                    if attempt < self._n_attempts:
                        self._queue.put((arg, attempt + 1))
                    else:
                        with self._elock:
                            self._exceptions[arg] = e

        # We spawn the required number of threads.

        with self._tlock:
            new_threads = self._n_threads - len(self._threads)
            for j in range(new_threads):
                tid = _generate_tid()
                thread = Thread(target = worker, args = (tid,))
                self._threads[tid] = thread
                thread.start()
            
    def add(self, arg, force = False):
        """Add a new input to the queue to be processed.

        Args:
            arg - the input to be processed. Must be hashable.
        """
        with self._ilock:
            if arg not in self._inputs or force:
                self._inputs.add(arg)
                self._queue.put((arg, 1))
                self._start()

    def add_many(self, args, force = False):
        """Add multiple new inputs to the queue to be processed.

        Args:
            args - an iterable that yields inputs. The inputs must be hashable.
        """
        with self._ilock:
            for arg in args:
                if arg not in self._inputs or force:
                    self._inputs.add(arg)
                    self._queue.put((arg, 1))
        self._start()

    def get_n_pending(self):
        """Get the number of pending inputs (not reliable!)
        """
        return self._queue.qsize()

    def get_n_finished(self):
        """Get the number of inputs for which processing was finished 
        successfully.
        """
        with self._rlock:
            return len(self._results)

    def get_n_running(self):
        """Get the number of inputs being processed right now (not reliable!)
        """
        with self._tlock:
            return len(self._threads) - self._n_paused

    def get_n_failed(self):
        """Get the number of inputs for which processing has raised an 
        exception.
        """
        with self._elock:
            return len(self._exceptions)

    def _get_status_string(self):
        """Get the status string (to be printed by self.print_status() or 
        self.wait().
        """
        stats = (self.get_n_pending(), 
                 self.get_n_running(), 
                 self.get_n_finished(), 
                 self.get_n_failed())
        template = "pending: {}\t running: {}\t finished: {}\t failed: {}"
        return template.format(*stats)

    def print_status(self):
        """Show the job's current status."""
        print(self._get_status_string())

    def wait(self, show_status = True, timeout = None):
        """Wait until all inputs are processed.

        KeyboardInterrupt can always be used to stop wait() safely.

        Args:
            show_status - a boolean. Determines whether to continuously show
                          the current running status.
            timeout - a number. If timeout is a non-negative number, the method
                      blocks for at most this number of seconds, and then
                      returns.
        """
        try:
            if timeout is not None:
                et = time() + timeout
            pt = time()
            if show_status:
                with _plock:
                    _show_status(self._get_status_string())
            while self.get_n_running() + self.get_n_pending() > 0:
                with self._tlock:
                    threads = list(self._threads.values())
                for thread in threads:
                    while thread.isAlive():
                        if timeout is None:
                            thread.join(timeout = 1)
                        else:
                            thread.join(timeout = min(1, et - time()))
                        ct = time()
                        if timeout is not None and ct >= et:
                            raise KeyboardInterrupt()
                        if ct >= pt + 1 and show_status:
                            pt = ct
                            with _plock:
                                _show_status(self._get_status_string())
            if show_status:
                with _plock:
                    _hide_status()
        except KeyboardInterrupt:
            if show_status and not _plock.locked():
                with _plock:
                    _hide_status()

    def set_n_threads(self, n):
        """See help(Job.__init__) for details."""
        self._n_threads = n
        self._start()

    def set_target(self, target, factory = False):
        """Replace the function to be applied for each input.

        This method is especially useful if you find a bug in your original
        target function, that caused exceptions for some inputs, but you are
        satisfied with the results you already have, and do not want to
        re-process them.

        See help(Job.__init__) for details about the requirements for a target
        function (or a target factory).
        """
        self._target = (target, factory)

    def set_n_attempts(self, n):
        """See help(Job.__init__) for details."""
        self._n_attempts = n

    def kill(self):
        """Kill all threads.
        
        Equivalent to set_n_threads(0).
        """
        self.set_n_threads(0)

    def pause(self):
        """Pause the job.

        It can be later resumed by Job.resume().
        """
        self._block.acquire(False)

    def resume(self):
        """Resume a paused job.

        A job can be paused by Job.pause().
        """
        self._block.release()

    def has_result(self, arg):
        """Check whether an input was processed successfully.

        If it has, the result can retrieved using Job.get_result().
        """
        with self._rlock:
            return arg in self._results

    def get_result(self, arg):
        """Get the result for a specific input.

        Raise an exception if the input was not processed successfully.
        """
        with self._rlock:
            return self._results[arg]

    def get_results(self):
        """Return a dictionary of all the results for all 
        the successfully-processed inputs.

        Note that if there are many results, costructing the dictionary may
        take some time, and running threads may be blocked during this time.
        """
        with self._rlock:
            results = self._results.copy()
        return results

    def has_exception(self, arg):
        """Check whether a specific input was processed but failed (the target
        function raised an exception).

        If it has, the exception can be retrieved using Job.get_exception().
        """
        with self._elock:
            return arg in self._exceptions

    def get_exception(self, arg):
        """Get the exception raised by the target function for the given input.
        
        Raise an exception if the input was not processed yet, or if it has 
        been processed successfully.
        """
        with self._elock:
            return self._exceptions[arg]

    def get_exceptions(self):
        """Return a dictionary of all the exceptions raised for all 
        the unsuccessfully-processed inputs.

        Note that if there are many such exception, costructing the dictionary
        may take some time, and running threads may be blocked during this 
        time (if the target function raises an exception).
        """
        with self._elock:
            exceptions = self._exceptions.copy()
        return exceptions

    def retry(self, arg):
        """Remove an input from the list of failed inputs, and put it back
        in the queue.
        """
        with self._elock:
            if arg in self._exceptions:
                del self._exceptions[arg]
        self.add(arg, force = True)

    def retry_many(self, args):
        """Remove multiple inputs from the list of failed inputs, and put them
        back in the queue.
        """
        for arg in args:
            self.retry(arg)

    def retry_all(self):
        """Remove all inputs from the list of failed inputs, and put them back
        in the queue.
        """
        with self._elock:
            args = []
            for arg in list(self._exceptions):
                del self._exceptions[arg]
                args.append(arg)
            self.add_many(args, force = True)

__all__ = ["Job", "print", "Lock"]
