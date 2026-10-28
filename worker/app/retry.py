# Decide what happens when classification, storage, or notification fails.
# Increment the attempt count, keep the ticket row, and set a time when the
# loop may claim it again. After the attempt limit you choose, set status failed.
# A failed ticket remains queryable through the status route.
