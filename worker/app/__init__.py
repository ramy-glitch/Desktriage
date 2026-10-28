# Worker application package.
# main starts the poll loop. The loop claims a ticket and hands it to the pipeline.
# The pipeline calls classifier, priority, confidence, review or routing, trace, and notify.
