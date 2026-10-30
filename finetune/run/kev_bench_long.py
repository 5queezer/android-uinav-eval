"""kev.benchmark on --data records with the serving context (65k states) instead of the 384-token training context."""
import kev.benchmark as b
import kev.suite as s

b.CONTEXT = s.SERVING_CONTEXT
b.main()
