FROM node:22-bookworm-slim AS frontend
WORKDIR /source/frontend
RUN corepack enable
COPY frontend/package.json frontend/yarn.lock frontend/.yarnrc.yml ./
RUN yarn install --immutable --mode=skip-build
COPY frontend/ ./
RUN yarn typecheck && yarn build

FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir "uv==0.12.12" && useradd --uid 10001 --create-home community
COPY pyproject.toml uv.lock LICENSE ./
RUN uv sync --locked --extra captcha --no-dev --no-cache
COPY app/ ./app/
# 随包数据文件缺失会让资料库昵称检索静默失效，构建期直接拦住。
RUN test -f app/tools/data/endfield_aliases.json
COPY main.py NOTICE.md ./
COPY docs/licenses/ ./docs/licenses/
COPY --from=frontend /source/frontend/dist/ ./frontend/dist/
RUN mkdir /data && chown community:community /data
USER community
ENV COMMUNITY_DATA_DIR=/data COMMUNITY_WEB_DIR=/app/frontend/dist
EXPOSE 37164
CMD ["/app/.venv/bin/python", "main.py", "--host", "0.0.0.0", "--remote"]
