## Create a new function in dog shit Azure web functions
```
func new --name HttpExample --template "HTTP trigger" --authlevel "anonymous"
```

## Run locally for testing
```shell
cd [this root directory]
source venv/bin/activate
func start
```