// vi: set expandtab ts=4 sw=4:

/*
 * === UCSF ChimeraX Copyright ===
 * Copyright 2016 Regents of the University of California.
 * All rights reserved.  This software provided pursuant to a
 * license agreement containing restrictions on its disclosure,
 * duplication and use.  For details see:
 * http://www.rbvi.ucsf.edu/chimerax/docs/licensing.html
 * This notice must be embedded in or attached to all copies,
 * including partial copies, of the software or any revisions
 * or derivations thereof.
 * === UCSF ChimeraX Copyright ===
 */

#ifndef pyinstance_python_instance_declare
#define pyinstance_python_instance_declare

#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <typeinfo>

#include "Python.h"

#include "imex.h"
#include "imex.map.h"

namespace pyinstance {

extern PYINSTANCE_MAP_IMEX std::map<const void*, PyObject*>  _pyinstance_object_map;

class PYINSTANCE_IMEX AcquireGIL {
public:
    AcquireGIL();
    ~AcquireGIL();
};

class PyAttrError : public std::runtime_error {
public:
    PyAttrError(const std::string msg) : std::runtime_error(msg) {}
};

class NoPyInstanceError : public PyAttrError {
public:
    NoPyInstanceError() : PyAttrError(std::string("No Python instance")) {}
    NoPyInstanceError(const std::string msg) : PyAttrError(msg) {}
};

class NoPyAttrError : public PyAttrError {
public:
    NoPyAttrError() : PyAttrError(std::string("Python instance has no such attr")) {}
    NoPyAttrError(const std::string msg) : PyAttrError(msg) {}
};

class WrongPyAttrTypeError : public PyAttrError {
public:
    WrongPyAttrTypeError() : PyAttrError(std::string("Python attr is wrong type")) {}
    WrongPyAttrTypeError(const std::string msg) : PyAttrError(msg) {}
};

// this is a template class so that different derived classes have separate static variables
template <class C>
class PYINSTANCE_IMEX PythonInstance {
private:
    static std::string  _buffer;  // so that the const char* from std::string will hang around
    static PyObject*  _py_class;
protected:
    static bool  make_py_destructor_callback;
public:
    virtual  ~PythonInstance();
    PyObject*  get_py_attr(const char* attr_name, bool create=false) const;
    double  get_py_float_attr(const char* attr_name, bool create=false) const;
    double  get_py_float_attr(std::string& attr_name, bool create=false) const;
    long  get_py_int_attr(const char* attr_name, bool create=false) const;
    long  get_py_int_attr(std::string& attr_name, bool create=false) const;
    const char*  get_py_string_attr(const char* attr_name, bool create=false) const;
    const char*  get_py_string_attr(std::string& attr_name, bool create=false) const;
    
    static PyObject*  py_class(); // returns a borrowed reference
    static void  set_py_class(PyObject* c_obj);
    std::string py_class_name() const;

    PyObject*  py_instance(bool create) const; // returns a new reference
    // some Python objects can't be created by C++ (need more args), so...
    void  set_py_instance(PyObject* py_obj);

    // limited to 0 or 1 arg methods; if you don't care about the return value, call Py_XDECREF on it
    PyObject* py_call_method(const std::string& method_name, const char* fmt=nullptr, const void* arg= nullptr) const;
};

}  // namespace pyinstance

#endif  // pyinstance_python_instance_declare
