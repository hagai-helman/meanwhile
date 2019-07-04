# meanwhile - Very Easy Multithreading

If you want to call the same function on many inputs, in a multithreaded 
fashion, ```meanwhile``` makes it easy.

It can make your code significantly faster, especially if the function requires
I/O operations, like file access or HTTP(S) queries.


## Installation

```bash
pip3 install meanwhile
```


## Simple Usage Example

Suppose you have a function named ```test_url```, that gets a URL, downloads
its content, and tests whether it contains the word "meanwhile". Also,
suppose you have a file, named ```urls.txt```, where each line contains a URL
you would like to apply ```test_url``` to.

You can do the following:

```python
>>> from meanwhile import Job
>>> job = Job(test_url, 10)    # at most 10 threads will be used concurrently.
>>> urls = open("urls.txt").read().splitlines()
>>> job.add_many(urls)
>>> job.wait()
>>> results = job.get_results()
```

The target function (in this case: ```test_url```) should get one argument, and
this argument should be hashable.

Note that if your function prints output, you probably want to use 
```meanwhile.print()``` instead of Python's built-in ```print()``` function.
This function prevents conflicts both with other threads, and with the progress
updates shown by the ```wait``` method.


## In More Details

The ```Job``` object holds a queue of inputs to process. It automatically 
spawns and kills threads, as needed (up to the maximal number of concurrent 
threads set by the user).

The methods ```add``` and ```add_many``` can be used to add inputs to the queue.

The method ```wait``` stops until the queue is empty. By default, it shows the
job's progress, like this:

```
pending: 19	 running: 20	 finished: 11	 failed: 0
```

In order to ```wait``` without showing the progress, one can set the keyword
argument ```show_status``` to be ```False```. Also, it's possible to show the
job's progress without ```wait```-ing, using the method ```print_status```.

```wait``` also supports a keyword argument, ```timeout```. If it is set, the
method will unconditionally return after ```timeout``` seconds. ```wait``` can
also be stopped safely by a ```KeyboardInterrupt```.

The return values of the target function can be inspected using the methods
```get_result```, ```has_result``` and ```get_results```.


## Fix Mistakes On The Fly

```meanwhile``` also makes it easy to debug your code and fix it while the job
is already in progress.

First, almost everything can be changed at any time. For example: 

* You can always add new inputs to the queue using ```add``` and ```add_many``` 
(even after all previous inputs were already processed, and all threads were 
killed); 
* You can always change the maximal number of threads allowed to run
  concurrently using the method ```set_n_threads```;
* You can always change the target function using the method ```set_target```
  (this will apply only to inputs that weren't successfully processed yet).

Also, you can inspect the exceptions raised by the target function using the
method ```get_exceptions``` (and also ```has_exception``` and
```get_exception```).

After you fix the cause for the exceptions, you can use the methods ```retry```,
```retry_many``` and ```retry_all``` to return inputs that raised exceptions
into the job's queue.

In case your target function sometimes randomly fails (i.e. raises exception),
you can also use the method ```set_n_attempts```, to make the job retry inputs
automatically for a limited number of attempts (and note that the ```Job``` 
class'es constructor also can take the keyword argument ```n_attempts```).

Finally, note the methods ```pause```, ```resume``` and ```kill```, that also
can be useful when you debug a job in progress (don't be afraid of ```kill```:
it is just equivalent to ```set_n_threads(0)```).


## Resource Reuse

Sometimes it's useful to have a thread reusing resources whlie sequentially 
processing inputs. For example, if your target function makes an HTTPS request,
you may want to reuse the same session, in order to save the TLS handshake time.

That's why ```meanwhile``` allows you to provide a target *factory* instead of a
target function. The factory is used to create a different target function for 
each thread spawned.

A target factory can be either a function that does not take arguments, and
returns a target function, or a callable class (that is initialized without
arguments, and its ```__call__``` method is used as the target function.

In order to provide a target factory instead of target function, one must set 
the keyword argument ```factory``` to be ```True``` (this is true for both the
```Job``` class constructor and the ```set_target``` method).


## Module Reference

For the full module reference, see ```help(meanwhile)```.
