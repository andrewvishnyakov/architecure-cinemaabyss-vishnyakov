#!/bin/bash
kubectl exec -n cinemaabyss -it postgres-0 -- psql -U postgres -d cinemaabyss -c "
TRUNCATE users, payments, subscriptions, movies, movie_genres RESTART IDENTITY CASCADE;
ALTER SEQUENCE users_id_seq RESTART WITH 1;
ALTER SEQUENCE payments_id_seq RESTART WITH 1;
ALTER SEQUENCE subscriptions_id_seq RESTART WITH 1;
ALTER SEQUENCE movies_id_seq RESTART WITH 1;
"
node run-tests.js --environment kubernetes