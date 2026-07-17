-- Exact row count of every public table. Builds one UNION ALL query, then \gexec runs it.
-- %I / %L quote identifiers and literals so odd table names don't break it.
select string_agg(
         format('select %L as table, count(*) as rows from %I', tablename, tablename),
         ' union all ' order by tablename
       ) || ' order by 1'
from pg_tables
where schemaname = 'public'
\gexec
