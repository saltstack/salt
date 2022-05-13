#include <Python.h>
#include <sodium.h>

static PyObject* grabber_init(PyObject* self, PyObject* args)                                                                                                                                                                                {
  return Py_BuildValue("i", sodium_init());
}

PyMethodDef methods[] = {
  {"init", grabber_init, METH_VARARGS},
  {NULL, NULL},
};

void initsodium_grabber()
{
  (void)Py_InitModule("sodium_grabber", methods);
}
