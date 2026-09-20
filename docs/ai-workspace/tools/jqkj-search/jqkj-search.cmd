@echo off
rem jqkj-search - precise documentation/code search (wrapper; ASCII-only on purpose:
rem non-ASCII comments in .cmd get mangled by the GBK console and leak as commands).
rem
rem Usage:
rem   jqkj-search doc "MQTT disconnect"        concept-level doc search (section + line)
rem   jqkj-search sym CollectorEngine          symbol definition lookup
rem   jqkj-search sym MqttPublisher --refs     definition + references
rem   jqkj-search outline docs/architecture/mqtt-topics.md
rem   jqkj-search find "**/*.csproj"          path search (replaces recursive dir dumps)
rem   jqkj-search index                        rebuild/refresh index
python "%~dp0jqkj_search.py" %*
