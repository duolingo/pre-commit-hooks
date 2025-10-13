build {
provisioner "shell" {
env = {
PATH = local.shell_path
HELLO_WORLD = var.hello_world
}
script = "scripts/hello-world.sh"
}
}
