# Judge0 setup (local)

Judge0 is the only component allowed to execute submitted Python code in V1.
Never use Python `exec` or `eval` in Django.

1. Obtain the external Judge0-compatible endpoint and, if required, its API key.
2. In the untracked `.env` file, set:

   ```text
   JUDGE0_BASE_URL=https://your-judge0-host
   JUDGE0_API_KEY=your-token-if-required
   ```

3. Run the connectivity spike:

   ```powershell
   python manage.py judge0_spike
   ```

Expected verdicts are `ACCEPTED`, `WRONG_ANSWER`, and `RUNTIME_ERROR`, in that
order. The command sends a known input/output pair only; it does not use any
hidden production test data.

If the endpoint does not require authentication, leave `JUDGE0_API_KEY` blank.
