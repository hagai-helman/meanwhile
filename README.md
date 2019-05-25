# meanwhile - Very Easy Multithreading

This module is useful when you want to apply the same function to many values,
and you want to do it in many threads. It's useful when the function requires
I/O operations, like file access or HTTP(S) queries.

## Installation

```bash
pip3 install meanwhile
```

## Simple Usage Example

Assume you have a function named ```test_url```, that gets a URL, downloads
its content, and tests whether it contains the word "meanwhile". Also,
assume you have a file, named ```urls.txt```, where each line contains a URL
you would like to apply ```test_url``` to.

You can do the following:

```python
>>> from meanwhile import Job
>>> job = Job(test_url, 10)    # 10 threads will be used.
>>> urls = open("urls.txt").read().splitlines()
>>> job.add_many(urls)
>>> job.wait()
>>> results = job.get_results()
```

Note that the function you apply to each input must get one argument, and that
this argument must be hashable.

Note that if your function prints output, you probably want to use 
```meanwhile.print()``` instead of the built-in ```print()``` function.

## Advanced Features

The module supports many useful features. For example, you can:

* Get progress info;
* Change the number of threads used;
* Pause and resume all threads;
* Add new inputs, when the job is already in progress, or even finished;
* Inspect exceptions raised by inputs;
* Replace the target function;
* Automatically or manually retry inputs that caused exceptions.

For full documentation, see ```help(meanwhile.Job)```.
