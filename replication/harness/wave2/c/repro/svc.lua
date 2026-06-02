-- HAProxy lua-service to drain request body and reply
core.register_service("upload", "http", function(applet)
    -- applet.body is the buffered request body (requires http-buffer-request)
    local body = applet.body or ""
    local len = applet.length or #body
    local resp = string.format('{"len":%d}', len)
    applet:set_status(200)
    applet:add_header("content-type", "application/json")
    applet:add_header("content-length", tostring(#resp))
    applet:start_response()
    applet:send(resp)
end)
