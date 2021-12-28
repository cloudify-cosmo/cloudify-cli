from cloudify import ctx

a = ctx.instance.runtime_properties.get('a', 0)
ctx.instance.runtime_properties['a'] = a + 1

